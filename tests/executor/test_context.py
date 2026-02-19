"""Tests for executor.context — ContextGenerator TASK.md generation."""

from __future__ import annotations

from pathlib import Path

from imp.executor.context import ContextGenerator
from imp.executor.models import ContextBudget, WorktreeSession


def _make_session(
    ticket_id: str = "IMP-001",
    title: str = "Add worktree manager",
    description: str = "Implement the WorktreeManager class",
) -> WorktreeSession:
    """Helper: create a WorktreeSession."""
    return WorktreeSession(ticket_id=ticket_id, title=title, description=description)


def _make_scan_data() -> dict:
    """Helper: sample scan_data dict."""
    return {
        "modules": [
            {"name": "imp.executor", "path": "src/imp/executor"},
            {"name": "imp.providers", "path": "src/imp/providers"},
        ]
    }


class TestContextGeneratorGenerate:
    """Test generate() method."""

    def test_generate_returns_string(self, tmp_path: Path) -> None:
        """generate() returns a string."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert isinstance(result, str)

    def test_generate_includes_ticket_id(self, tmp_path: Path) -> None:
        """generate() includes the ticket ID in output."""
        gen = ContextGenerator(tmp_path)
        session = _make_session("IMP-007")
        result = gen.generate(session)
        assert "IMP-007" in result

    def test_generate_includes_title(self, tmp_path: Path) -> None:
        """generate() includes the session title."""
        gen = ContextGenerator(tmp_path)
        session = _make_session(title="Implement the thing")
        result = gen.generate(session)
        assert "Implement the thing" in result

    def test_generate_includes_description(self, tmp_path: Path) -> None:
        """generate() includes the session description in Goal section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session(description="Detailed feature description here")
        result = gen.generate(session)
        assert "Detailed feature description here" in result

    def test_generate_includes_goal_section(self, tmp_path: Path) -> None:
        """generate() includes a ## Goal section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Goal" in result

    def test_generate_includes_project_structure_section(self, tmp_path: Path) -> None:
        """generate() includes a ## Project Structure section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Project Structure" in result

    def test_generate_includes_conventions_section(self, tmp_path: Path) -> None:
        """generate() includes a ## Conventions section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Conventions" in result

    def test_generate_includes_data_locations_section(self, tmp_path: Path) -> None:
        """generate() includes a ## Data Locations section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Data Locations" in result

    def test_generate_includes_expected_output_section(self, tmp_path: Path) -> None:
        """generate() includes a ## Expected Output section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Expected Output" in result

    def test_generate_includes_all_five_sections(self, tmp_path: Path) -> None:
        """generate() includes all 5 required sections."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Goal" in result
        assert "## Project Structure" in result
        assert "## Conventions" in result
        assert "## Data Locations" in result
        assert "## Expected Output" in result

    def test_generate_includes_context_budget_section(self, tmp_path: Path) -> None:
        """generate() includes a context budget section."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "## Context Budget" in result

    def test_generate_includes_context_budget_values(self, tmp_path: Path) -> None:
        """generate() includes used/max token counts."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-001",
            title="Test",
            context_budget=ContextBudget(max_tokens=200_000, used_tokens=10_000),
        )
        result = gen.generate(session)
        # Should show used/max somewhere
        assert "10000" in result or "10,000" in result
        assert "200000" in result or "200,000" in result

    def test_generate_includes_no_refactor_rule(self, tmp_path: Path) -> None:
        """generate() injects 'do NOT refactor outside ticket scope' rule."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        # Case-insensitive check for the rule
        assert "refactor" in result.lower()
        assert "ticket" in result.lower()

    def test_generate_includes_imp_check_rule(self, tmp_path: Path) -> None:
        """generate() includes instruction to run imp check."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "imp check" in result

    def test_generate_includes_imp_review_rule(self, tmp_path: Path) -> None:
        """generate() includes instruction to run imp review."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "imp review" in result

    def test_generate_uses_scan_data_when_provided(self, tmp_path: Path) -> None:
        """generate() uses module list from scan_data when provided."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        scan_data = _make_scan_data()
        result = gen.generate(session, scan_data=scan_data)
        # Should include module names from scan_data
        assert "imp.executor" in result or "imp.providers" in result

    def test_generate_uses_fallback_when_scan_data_is_none(self, tmp_path: Path) -> None:
        """generate() uses fallback text when scan_data is None."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session, scan_data=None)
        # Fallback instructs to run imp init
        assert "imp init" in result

    def test_generate_minimal_session_no_description(self, tmp_path: Path) -> None:
        """generate() works correctly when description is empty."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(ticket_id="IMP-001", title="Minimal")
        result = gen.generate(session)
        # Should still produce output with all sections
        assert "## Goal" in result
        assert "## Expected Output" in result

    def test_generate_includes_index_md_reference(self, tmp_path: Path) -> None:
        """generate() references .index.md for codebase navigation."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert ".index.md" in result

    def test_generate_includes_three_tier_tdd_convention(self, tmp_path: Path) -> None:
        """generate() mentions three-tier TDD convention."""
        gen = ContextGenerator(tmp_path)
        session = _make_session()
        result = gen.generate(session)
        assert "TDD" in result or "tests" in result.lower()

    def test_generate_with_full_inputs(self, tmp_path: Path) -> None:
        """generate() with all inputs produces complete TASK.md content."""
        gen = ContextGenerator(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-042",
            title="Implement feature X",
            description="Add feature X to improve performance",
            context_budget=ContextBudget(max_tokens=200_000, used_tokens=25_000),
        )
        scan_data = _make_scan_data()
        result = gen.generate(session, scan_data=scan_data)

        # Should have all expected pieces
        assert "IMP-042" in result
        assert "Implement feature X" in result
        assert "Add feature X to improve performance" in result
        assert "## Goal" in result
        assert "## Project Structure" in result
        assert "## Conventions" in result
        assert "## Data Locations" in result
        assert "## Expected Output" in result
        assert "## Context Budget" in result


class TestContextGeneratorWriteTaskFile:
    """Test write_task_file() method."""

    def test_write_task_file_creates_task_md(self, tmp_path: Path) -> None:
        """write_task_file() creates TASK.md in the worktree directory."""
        gen = ContextGenerator(tmp_path)
        worktree_path = tmp_path / ".trees" / "IMP-001"
        worktree_path.mkdir(parents=True)

        content = "# Task: Test\n\n## Goal\nTest goal\n"
        gen.write_task_file(worktree_path, content)

        task_md = worktree_path / "TASK.md"
        assert task_md.exists()

    def test_write_task_file_writes_content(self, tmp_path: Path) -> None:
        """write_task_file() writes the exact content to TASK.md."""
        gen = ContextGenerator(tmp_path)
        worktree_path = tmp_path / ".trees" / "IMP-001"
        worktree_path.mkdir(parents=True)

        content = "# Task: Test\n\n## Goal\nDo the thing.\n"
        gen.write_task_file(worktree_path, content)

        task_md = worktree_path / "TASK.md"
        assert task_md.read_text() == content

    def test_write_task_file_returns_correct_path(self, tmp_path: Path) -> None:
        """write_task_file() returns the path to TASK.md."""
        gen = ContextGenerator(tmp_path)
        worktree_path = tmp_path / ".trees" / "IMP-001"
        worktree_path.mkdir(parents=True)

        content = "# Task content"
        result = gen.write_task_file(worktree_path, content)

        expected = worktree_path / "TASK.md"
        assert result == expected

    def test_write_task_file_returns_path_instance(self, tmp_path: Path) -> None:
        """write_task_file() returns a Path instance."""
        gen = ContextGenerator(tmp_path)
        worktree_path = tmp_path / ".trees" / "IMP-001"
        worktree_path.mkdir(parents=True)

        result = gen.write_task_file(worktree_path, "content")
        assert isinstance(result, Path)

    def test_write_task_file_overwrites_existing(self, tmp_path: Path) -> None:
        """write_task_file() overwrites an existing TASK.md."""
        gen = ContextGenerator(tmp_path)
        worktree_path = tmp_path / ".trees" / "IMP-001"
        worktree_path.mkdir(parents=True)

        # Write initial content
        gen.write_task_file(worktree_path, "old content")
        # Overwrite with new content
        gen.write_task_file(worktree_path, "new content")

        task_md = worktree_path / "TASK.md"
        assert task_md.read_text() == "new content"

    def test_generate_and_write_integration(self, tmp_path: Path) -> None:
        """generate() output can be written by write_task_file()."""
        gen = ContextGenerator(tmp_path)
        session = _make_session("IMP-010", "Integration test")

        worktree_path = tmp_path / ".trees" / "IMP-010"
        worktree_path.mkdir(parents=True)

        content = gen.generate(session)
        path = gen.write_task_file(worktree_path, content)

        assert path.exists()
        written = path.read_text()
        assert "IMP-010" in written
        assert "Integration test" in written
