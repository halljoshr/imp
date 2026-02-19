"""WorktreeManager — subprocess-based git worktree operations."""

from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeError(Exception):
    """Raised when a git worktree operation fails."""


class WorktreeManager:
    """Manages git worktrees for executor sessions via subprocess."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a subprocess command, raising WorktreeError on failure."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.CalledProcessError as exc:
            raise WorktreeError(str(exc)) from exc
        return result

    def current_branch(self) -> str:
        """Get the current git branch name.

        Returns:
            The current branch name (e.g. 'main', 'feat/executor').

        Raises:
            WorktreeError: If the git command fails.
        """
        cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        result = self._run(cmd)
        if result.returncode != 0:
            raise WorktreeError(result.stderr)
        return result.stdout.strip()

    def create(self, ticket_id: str, base_branch: str = "main") -> Path:
        """Create a new worktree for the ticket. Returns the worktree path."""
        worktree_path = f".trees/{ticket_id}"
        branch = f"imp/{ticket_id}"
        cmd = ["git", "worktree", "add", "-b", branch, worktree_path, base_branch]
        result = self._run(cmd)
        if result.returncode != 0:
            raise WorktreeError(result.stderr)
        return self._repo_root / worktree_path

    def remove(self, ticket_id: str) -> None:
        """Remove the worktree for the given ticket."""
        worktree_path = f".trees/{ticket_id}"
        cmd = ["git", "worktree", "remove", worktree_path]
        result = self._run(cmd)
        if result.returncode != 0:
            raise WorktreeError(result.stderr)

    def list_worktrees(self) -> list[dict[str, str]]:
        """List all worktrees, parsed from git's porcelain output."""
        cmd = ["git", "worktree", "list", "--porcelain"]
        result = self._run(cmd)
        if not result.stdout:
            return []
        return self._parse_porcelain(result.stdout)

    def _parse_porcelain(self, output: str) -> list[dict[str, str]]:
        """Parse git worktree list --porcelain output into dicts."""
        trees: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in output.splitlines():
            if line == "":
                if current:
                    trees.append(current)
                    current = {}
            else:
                key, _, value = line.partition(" ")
                current[key] = value
        if current:
            trees.append(current)
        return trees

    def exists(self, ticket_id: str) -> bool:
        """Return True if a worktree for the ticket exists."""
        worktree_path = f".trees/{ticket_id}"
        trees = self.list_worktrees()
        return any(worktree_path in t.get("worktree", "") for t in trees)

    def prune(self) -> None:
        """Prune stale worktree admin files."""
        cmd = ["git", "worktree", "prune"]
        result = self._run(cmd)
        if result.returncode != 0:
            raise WorktreeError(result.stderr)

    def delete_branch(self, ticket_id: str, force: bool = False) -> None:
        """Delete the branch for the given ticket."""
        branch = f"imp/{ticket_id}"
        flag = "-D" if force else "-d"
        cmd = ["git", "branch", flag, branch]
        result = self._run(cmd)
        if result.returncode != 0:
            raise WorktreeError(result.stderr)
