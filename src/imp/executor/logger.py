"""DecisionLogger — logs completion decisions to .imp/decisions/."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from imp.executor.models import CompletionAttempt, DecisionEntry


class DecisionLogger:
    """Logs completion decisions to .imp/decisions/{ticket_id}.json."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.decisions_dir = project_root / ".imp" / "decisions"

    def log_completion(
        self,
        ticket_id: str,
        attempts: list[CompletionAttempt],
        outcome: str,
        worktree_path: Path,
    ) -> DecisionEntry:
        """Log a completion decision. Runs git diff --stat in worktree."""
        self.decisions_dir.mkdir(parents=True, exist_ok=True)

        files_changed, diff_summary = self._get_diff_info(worktree_path)

        entry = DecisionEntry(
            ticket_id=ticket_id,
            timestamp=datetime.now(UTC),
            files_changed=files_changed,
            diff_summary=diff_summary,
            attempt_history=attempts,
            outcome=outcome,
        )

        path = self.decisions_dir / f"{ticket_id}.json"
        path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
        return entry

    def _get_diff_info(self, worktree_path: Path) -> tuple[list[str], str]:
        """Run git diff --stat HEAD and parse output."""
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return [], ""

        output = result.stdout
        files: list[str] = []
        for line in output.splitlines():
            # File lines look like: " src/foo.py | 10 +++"
            if "|" in line:
                file_part = line.split("|")[0].strip()
                if file_part:
                    files.append(file_part)

        return files, output

    def load(self, ticket_id: str) -> DecisionEntry | None:
        """Load a decision entry by ticket_id, or None if not found."""
        path = self.decisions_dir / f"{ticket_id}.json"
        if not path.exists():
            return None
        return DecisionEntry.model_validate_json(path.read_text(encoding="utf-8"))

    def list_decisions(self) -> list[DecisionEntry]:
        """Return all logged decision entries."""
        if not self.decisions_dir.exists():
            return []
        entries: list[DecisionEntry] = []
        for json_file in self.decisions_dir.glob("*.json"):
            entries.append(
                DecisionEntry.model_validate_json(json_file.read_text(encoding="utf-8"))
            )
        return entries
