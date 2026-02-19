"""SessionStore — JSON-backed persistence for WorktreeSession objects."""

from __future__ import annotations

import json
from pathlib import Path

from imp.executor.models import WorktreeSession


class SessionStore:
    """Stores and retrieves WorktreeSession objects as JSON files."""

    def __init__(self, project_root: Path) -> None:
        self._sessions_dir = project_root / ".imp" / "sessions"

    def _session_path(self, ticket_id: str) -> Path:
        return self._sessions_dir / f"{ticket_id}.json"

    def save(self, session: WorktreeSession) -> None:
        """Persist a session to disk, creating the directory if needed."""
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self._session_path(session.ticket_id)
        path.write_text(session.model_dump_json(), encoding="utf-8")

    def load(self, ticket_id: str) -> WorktreeSession | None:
        """Load a session by ticket_id, or None if not found."""
        path = self._session_path(ticket_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorktreeSession.model_validate(data)

    def list_sessions(self) -> list[WorktreeSession]:
        """Return all saved sessions."""
        if not self._sessions_dir.exists():
            return []
        sessions = []
        for json_file in self._sessions_dir.glob("*.json"):
            data = json.loads(json_file.read_text(encoding="utf-8"))
            sessions.append(WorktreeSession.model_validate(data))
        return sessions

    def delete(self, ticket_id: str) -> bool:
        """Delete a session. Returns True if it existed, False otherwise."""
        path = self._session_path(ticket_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def exists(self, ticket_id: str) -> bool:
        """Return True if a session with the given ticket_id exists."""
        return self._session_path(ticket_id).exists()
