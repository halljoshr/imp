"""Tests for summary cache — load/save AI summaries for modules."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

# ===== SummaryEntry Model Tests =====


def test_summary_entry_construction() -> None:
    """Test SummaryEntry can be constructed with required fields."""
    from imp.context.summary_cache import SummaryEntry

    entry = SummaryEntry(
        purpose="Handles user authentication and session management.",
        summarized_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        model_used="anthropic:claude-haiku-4-5",
    )
    assert entry.purpose == "Handles user authentication and session management."
    assert entry.model_used == "anthropic:claude-haiku-4-5"
    assert entry.summarized_at.year == 2025


def test_summary_entry_is_frozen() -> None:
    """Test SummaryEntry is immutable."""
    from imp.context.summary_cache import SummaryEntry

    entry = SummaryEntry(
        purpose="Test purpose.",
        summarized_at=datetime.now(UTC),
        model_used="test-model",
    )
    with pytest.raises(ValidationError):
        entry.purpose = "Changed"  # type: ignore[misc]


def test_summary_entry_serialization() -> None:
    """Test SummaryEntry round-trips through JSON."""
    from imp.context.summary_cache import SummaryEntry

    entry = SummaryEntry(
        purpose="Core business logic.",
        summarized_at=datetime(2025, 6, 1, 10, 30, 0, tzinfo=UTC),
        model_used="anthropic:claude-haiku-4-5",
    )
    json_str = entry.model_dump_json()
    loaded = SummaryEntry.model_validate_json(json_str)
    assert loaded.purpose == entry.purpose
    assert loaded.model_used == entry.model_used
    assert loaded.summarized_at == entry.summarized_at


# ===== save_summaries Tests =====


def test_save_summaries_creates_file(tmp_path: Path) -> None:
    """Test save_summaries writes .imp/summaries.json."""
    from imp.context.summary_cache import SummaryEntry, save_summaries

    summaries = {
        "src/": SummaryEntry(
            purpose="Source code.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        ),
    }
    result_path = save_summaries(summaries, tmp_path)

    assert result_path == tmp_path / ".imp" / "summaries.json"
    assert result_path.exists()


def test_save_summaries_creates_imp_dir(tmp_path: Path) -> None:
    """Test save_summaries creates .imp/ directory if needed."""
    from imp.context.summary_cache import SummaryEntry, save_summaries

    summaries = {
        "src/": SummaryEntry(
            purpose="Source code.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        ),
    }
    save_summaries(summaries, tmp_path)

    assert (tmp_path / ".imp").is_dir()


def test_save_summaries_valid_json(tmp_path: Path) -> None:
    """Test save_summaries writes valid JSON."""
    from imp.context.summary_cache import SummaryEntry, save_summaries

    summaries = {
        "src/": SummaryEntry(
            purpose="Source code.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        ),
        "tests/": SummaryEntry(
            purpose="Test suite.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        ),
    }
    result_path = save_summaries(summaries, tmp_path)
    data = json.loads(result_path.read_text())

    assert isinstance(data, dict)
    assert "src/" in data
    assert "tests/" in data
    assert data["src/"]["purpose"] == "Source code."


def test_save_summaries_empty_dict(tmp_path: Path) -> None:
    """Test save_summaries with empty dict writes empty JSON object."""
    from imp.context.summary_cache import save_summaries

    result_path = save_summaries({}, tmp_path)
    data = json.loads(result_path.read_text())
    assert data == {}


# ===== load_summaries Tests =====


def test_load_summaries_round_trip(tmp_path: Path) -> None:
    """Test load/save round-trip preserves data."""
    from imp.context.summary_cache import SummaryEntry, load_summaries, save_summaries

    original = {
        "src/": SummaryEntry(
            purpose="Source code.",
            summarized_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
            model_used="anthropic:claude-haiku-4-5",
        ),
        "tests/": SummaryEntry(
            purpose="Test suite.",
            summarized_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
            model_used="anthropic:claude-haiku-4-5",
        ),
    }
    save_summaries(original, tmp_path)
    loaded = load_summaries(tmp_path)

    assert len(loaded) == 2
    assert loaded["src/"].purpose == "Source code."
    assert loaded["tests/"].purpose == "Test suite."
    assert loaded["src/"].model_used == "anthropic:claude-haiku-4-5"


def test_load_summaries_missing_file(tmp_path: Path) -> None:
    """Test load_summaries returns empty dict when file doesn't exist."""
    from imp.context.summary_cache import load_summaries

    result = load_summaries(tmp_path)
    assert result == {}


def test_load_summaries_corrupt_file(tmp_path: Path) -> None:
    """Test load_summaries returns empty dict for corrupt JSON."""
    from imp.context.summary_cache import load_summaries

    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir()
    (imp_dir / "summaries.json").write_text("not valid json {{{")

    result = load_summaries(tmp_path)
    assert result == {}


def test_load_summaries_invalid_structure(tmp_path: Path) -> None:
    """Test load_summaries returns empty dict for valid JSON but invalid structure."""
    from imp.context.summary_cache import load_summaries

    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir()
    # Valid JSON but wrong shape — values aren't SummaryEntry
    (imp_dir / "summaries.json").write_text('{"src/": "not a summary entry"}')

    result = load_summaries(tmp_path)
    assert result == {}
