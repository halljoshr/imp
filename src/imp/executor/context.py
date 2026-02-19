"""ContextGenerator — generates TASK.md content for executor sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from imp.executor.models import WorktreeSession


class ContextGenerator:
    """Generates TASK.md context files for managed executor sessions."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def generate(self, session: WorktreeSession, scan_data: dict[str, Any] | None = None) -> str:
        """Generate TASK.md content for the given session."""
        budget = session.context_budget
        used = budget.used_tokens
        max_t = budget.max_tokens

        if scan_data is not None:
            modules = scan_data.get("modules", [])
            module_lines = "\n".join(f"- `{m['name']}` → `{m['path']}`" for m in modules)
            structure_body = (
                f"Scanned modules:\n{module_lines}\n\n"
                "See `.index.md` in each package directory for detailed navigation."
            )
        else:
            structure_body = (
                "Run `imp init` to generate the index, then read `.index.md` "
                "for codebase navigation."
            )

        content = f"""\
# TASK: {session.ticket_id} — {session.title}

## Goal

**Ticket:** {session.ticket_id}
**Title:** {session.title}

{session.description}

## Project Structure

{structure_body}

## Conventions

- Three-tier TDD: unit tests → integration tests → smoke tests, ALL written before implementation.
- Run `imp check` after every change to validate (tests, lint, type, format).
- Run `imp review` when all checks pass to get AI review before committing.
- Do NOT refactor outside ticket scope — stay focused on what the ticket requires.
- 100% branch coverage required. No exceptions.
- Python 3.12+, `from __future__ import annotations` in every file.
- Pydantic v2 models, strict mypy typing, line length 99.

## Data Locations

- Source: `src/imp/`
- Tests: `tests/`
- Index: `.index.md` in each package directory
- Session data: `.imp/sessions/`
- Plans: `.imp/plans/`
- Summaries: `.imp/summaries.json`

## Expected Output

When the ticket is complete:
1. All `imp check` gates pass (tests, lint, type, format).
2. `imp review` returns no blocking issues.
3. Code is committed on branch `{session.branch}`.
4. No changes outside the ticket scope.

## Context Budget

- Used: {used:,} / {max_t:,} tokens ({budget.usage_pct:.1f}%)
- Available: {budget.available_tokens:,} tokens
- Reserved: {budget.reserved_tokens:,} tokens

Keep responses focused and avoid loading unnecessary files to preserve context budget.
"""
        return content

    def write_task_file(self, worktree_path: Path, content: str) -> Path:
        """Write TASK.md to the worktree directory. Returns the path."""
        task_md = worktree_path / "TASK.md"
        task_md.write_text(content, encoding="utf-8")
        return task_md
