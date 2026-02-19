"""Tests for executor.session — SessionStore persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from imp.executor.models import ContextBudget, SessionStatus, WorktreeSession
from imp.executor.session import SessionStore


def _make_session(ticket_id: str = "IMP-001", title: str = "Test ticket") -> WorktreeSession:
    """Helper: create a minimal WorktreeSession."""
    return WorktreeSession(ticket_id=ticket_id, title=title)


class TestSessionStoreSaveLoad:
    """Test save and load roundtrip."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Saving and loading a session preserves all fields."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-001", "Roundtrip test")
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.ticket_id == "IMP-001"
        assert loaded.title == "Roundtrip test"

    def test_save_preserves_status(self, tmp_path: Path) -> None:
        """Saving preserves status field."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-001")
        session.status = SessionStatus.done
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.status == SessionStatus.done

    def test_save_preserves_attempt_count(self, tmp_path: Path) -> None:
        """Saving preserves attempt_count field."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-001")
        session.attempt_count = 2
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.attempt_count == 2

    def test_save_preserves_description(self, tmp_path: Path) -> None:
        """Saving preserves description field."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-001",
            title="Test",
            description="A detailed description",
        )
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.description == "A detailed description"

    def test_save_preserves_branch(self, tmp_path: Path) -> None:
        """Saving preserves computed branch field."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-005")
        store.save(session)

        loaded = store.load("IMP-005")
        assert loaded is not None
        assert loaded.branch == "imp/IMP-005"

    def test_save_preserves_worktree_path(self, tmp_path: Path) -> None:
        """Saving preserves computed worktree_path field."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-007")
        store.save(session)

        loaded = store.load("IMP-007")
        assert loaded is not None
        assert loaded.worktree_path == ".trees/IMP-007"

    def test_save_preserves_context_budget(self, tmp_path: Path) -> None:
        """Saving preserves context_budget field."""
        store = SessionStore(tmp_path)
        session = WorktreeSession(
            ticket_id="IMP-001",
            title="Test",
            context_budget=ContextBudget(used_tokens=12_000),
        )
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.context_budget.used_tokens == 12_000

    def test_save_preserves_created_at(self, tmp_path: Path) -> None:
        """Saving preserves created_at timestamp."""
        store = SessionStore(tmp_path)
        created = datetime.now(UTC)
        session = WorktreeSession(ticket_id="IMP-001", title="Test", created_at=created)
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        # Compare by isoformat string to avoid microsecond drift
        assert loaded.created_at.isoformat() == created.isoformat()

    def test_overwrite_existing_session(self, tmp_path: Path) -> None:
        """Saving the same ticket_id overwrites the existing session."""
        store = SessionStore(tmp_path)
        session = _make_session("IMP-001")
        store.save(session)

        session.status = SessionStatus.done
        session.attempt_count = 3
        store.save(session)

        loaded = store.load("IMP-001")
        assert loaded is not None
        assert loaded.status == SessionStatus.done
        assert loaded.attempt_count == 3


class TestSessionStoreLoad:
    """Test load behavior for missing sessions."""

    def test_load_returns_none_for_nonexistent(self, tmp_path: Path) -> None:
        """load() returns None for a ticket_id that does not exist."""
        store = SessionStore(tmp_path)
        assert store.load("IMP-MISSING") is None

    def test_load_returns_none_when_store_empty(self, tmp_path: Path) -> None:
        """load() returns None when no sessions have been saved."""
        store = SessionStore(tmp_path)
        assert store.load("IMP-001") is None


class TestSessionStoreList:
    """Test list_sessions behavior."""

    def test_list_sessions_empty(self, tmp_path: Path) -> None:
        """list_sessions() returns empty list when no sessions saved."""
        store = SessionStore(tmp_path)
        assert store.list_sessions() == []

    def test_list_sessions_single(self, tmp_path: Path) -> None:
        """list_sessions() returns one session after one save."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].ticket_id == "IMP-001"

    def test_list_sessions_multiple(self, tmp_path: Path) -> None:
        """list_sessions() returns all saved sessions."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        store.save(_make_session("IMP-002"))
        store.save(_make_session("IMP-003"))

        sessions = store.list_sessions()
        ticket_ids = {s.ticket_id for s in sessions}
        assert ticket_ids == {"IMP-001", "IMP-002", "IMP-003"}

    def test_list_sessions_returns_worktree_session_instances(self, tmp_path: Path) -> None:
        """list_sessions() returns WorktreeSession instances."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        sessions = store.list_sessions()
        assert all(isinstance(s, WorktreeSession) for s in sessions)


class TestSessionStoreDelete:
    """Test delete behavior."""

    def test_delete_removes_session(self, tmp_path: Path) -> None:
        """delete() removes the session so it can no longer be loaded."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        store.delete("IMP-001")
        assert store.load("IMP-001") is None

    def test_delete_returns_true_when_existed(self, tmp_path: Path) -> None:
        """delete() returns True when the session existed."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        result = store.delete("IMP-001")
        assert result is True

    def test_delete_returns_false_for_nonexistent(self, tmp_path: Path) -> None:
        """delete() returns False when session does not exist."""
        store = SessionStore(tmp_path)
        result = store.delete("IMP-MISSING")
        assert result is False

    def test_delete_does_not_affect_other_sessions(self, tmp_path: Path) -> None:
        """delete() only removes the specified session."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        store.save(_make_session("IMP-002"))
        store.delete("IMP-001")

        assert store.load("IMP-001") is None
        assert store.load("IMP-002") is not None


class TestSessionStoreExists:
    """Test exists behavior."""

    def test_exists_true_when_saved(self, tmp_path: Path) -> None:
        """exists() returns True after session is saved."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        assert store.exists("IMP-001") is True

    def test_exists_false_when_not_saved(self, tmp_path: Path) -> None:
        """exists() returns False when no session has been saved."""
        store = SessionStore(tmp_path)
        assert store.exists("IMP-001") is False

    def test_exists_false_after_delete(self, tmp_path: Path) -> None:
        """exists() returns False after the session is deleted."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))
        store.delete("IMP-001")
        assert store.exists("IMP-001") is False


class TestSessionStoreDirectoryCreation:
    """Test directory auto-creation behavior."""

    def test_sessions_dir_created_on_first_save(self, tmp_path: Path) -> None:
        """The .imp/sessions/ directory is auto-created on first save."""
        store = SessionStore(tmp_path)
        sessions_dir = tmp_path / ".imp" / "sessions"
        assert not sessions_dir.exists()

        store.save(_make_session("IMP-001"))
        assert sessions_dir.exists()
        assert sessions_dir.is_dir()

    def test_saves_to_correct_path(self, tmp_path: Path) -> None:
        """Session is saved to .imp/sessions/{ticket_id}.json."""
        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-042"))

        expected_path = tmp_path / ".imp" / "sessions" / "IMP-042.json"
        assert expected_path.exists()

    def test_json_file_is_valid(self, tmp_path: Path) -> None:
        """The saved JSON file is valid and parseable."""
        import json

        store = SessionStore(tmp_path)
        store.save(_make_session("IMP-001"))

        json_path = tmp_path / ".imp" / "sessions" / "IMP-001.json"
        content = json_path.read_text()
        data = json.loads(content)
        assert data["ticket_id"] == "IMP-001"
