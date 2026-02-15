"""Tests for staleness detection — detect modules that need re-scanning."""

from datetime import UTC, datetime
from pathlib import Path

from imp.context.models import (
    DirectoryModule,
    FileInfo,
    Language,
    ModuleInfo,
    ProjectScan,
)

# ===== Helpers =====


def _make_file(path: str, line_count: int = 10) -> ModuleInfo:
    """Build a minimal ModuleInfo for testing."""
    return ModuleInfo(
        file_info=FileInfo(
            path=path,
            size_bytes=line_count * 40,
            language=Language.PYTHON,
            line_count=line_count,
        ),
    )


def _make_scan(
    modules: list[DirectoryModule],
    scanned_at: datetime | None = None,
) -> ProjectScan:
    """Build a ProjectScan for testing."""
    if scanned_at is None:
        scanned_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    total_files = sum(len(m.files) for m in modules)
    return ProjectScan(
        project_root="/tmp/project",
        project_type="python",
        modules=modules,
        total_files=total_files,
        total_functions=0,
        total_classes=0,
        scanned_at=scanned_at,
    )


# ===== StaleModule Model Tests =====


def test_stale_module_construction() -> None:
    """Test StaleModule can be constructed."""
    from imp.context.staleness import StaleModule

    stale = StaleModule(
        module_path="src/",
        reason="files_modified",
        changed_files=["src/main.py"],
    )
    assert stale.module_path == "src/"
    assert stale.reason == "files_modified"
    assert stale.changed_files == ["src/main.py"]


# ===== detect_stale_modules Tests =====


def test_detect_no_changes() -> None:
    """Test no stale modules when scans are identical."""
    from imp.context.staleness import detect_stale_modules

    modules = [
        DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
    ]
    previous = _make_scan(modules)
    current = _make_scan(modules)

    stale = detect_stale_modules(current, previous)
    assert stale == []


def test_detect_new_module() -> None:
    """Test detecting a newly added module."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
            DirectoryModule(path="tests/", files=[_make_file("tests/test_main.py")]),
        ]
    )

    stale = detect_stale_modules(current, previous)
    assert len(stale) == 1
    assert stale[0].module_path == "tests/"
    assert stale[0].reason == "module_added"


def test_detect_deleted_module() -> None:
    """Test detecting a deleted module."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
            DirectoryModule(path="old/", files=[_make_file("old/legacy.py")]),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
        ]
    )

    stale = detect_stale_modules(current, previous)
    assert len(stale) == 1
    assert stale[0].module_path == "old/"
    assert stale[0].reason == "module_deleted"


def test_detect_files_added_to_module() -> None:
    """Test detecting new files added to an existing module."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(
                path="src/",
                files=[_make_file("src/main.py"), _make_file("src/utils.py")],
            ),
        ]
    )

    stale = detect_stale_modules(current, previous)
    assert len(stale) == 1
    assert stale[0].module_path == "src/"
    assert stale[0].reason == "files_added"
    assert "src/utils.py" in stale[0].changed_files


def test_detect_files_deleted_from_module() -> None:
    """Test detecting files removed from an existing module."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(
                path="src/",
                files=[_make_file("src/main.py"), _make_file("src/old.py")],
            ),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
        ]
    )

    stale = detect_stale_modules(current, previous)
    assert len(stale) == 1
    assert stale[0].module_path == "src/"
    assert stale[0].reason == "files_deleted"
    assert "src/old.py" in stale[0].changed_files


def test_detect_files_modified() -> None:
    """Test detecting modified files (different line_count/size)."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py", line_count=10)]),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py", line_count=20)]),
        ]
    )

    stale = detect_stale_modules(current, previous)
    assert len(stale) == 1
    assert stale[0].module_path == "src/"
    assert stale[0].reason == "files_modified"
    assert "src/main.py" in stale[0].changed_files


def test_detect_multiple_changes() -> None:
    """Test detecting multiple types of changes across modules."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py", line_count=10)]),
            DirectoryModule(path="old/", files=[_make_file("old/legacy.py")]),
        ]
    )
    current = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py", line_count=20)]),
            DirectoryModule(path="new/", files=[_make_file("new/fresh.py")]),
        ]
    )

    stale = detect_stale_modules(current, previous)
    # src/ modified, old/ deleted, new/ added
    assert len(stale) == 3
    paths = {s.module_path for s in stale}
    assert paths == {"src/", "old/", "new/"}


def test_detect_empty_scans() -> None:
    """Test staleness detection with empty scans."""
    from imp.context.staleness import detect_stale_modules

    previous = _make_scan([])
    current = _make_scan([])
    stale = detect_stale_modules(current, previous)
    assert stale == []


# ===== load_previous_scan Tests =====


def test_load_previous_scan_exists(tmp_path: Path) -> None:
    """Test loading a previous scan from .imp/scan.json."""
    from imp.context.staleness import load_previous_scan

    scan = _make_scan(
        [
            DirectoryModule(path="src/", files=[_make_file("src/main.py")]),
        ]
    )
    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir()
    (imp_dir / "scan.json").write_text(scan.model_dump_json(indent=2))

    loaded = load_previous_scan(tmp_path)
    assert loaded is not None
    assert loaded.project_type == "python"
    assert len(loaded.modules) == 1


def test_load_previous_scan_missing(tmp_path: Path) -> None:
    """Test loading when .imp/scan.json doesn't exist."""
    from imp.context.staleness import load_previous_scan

    result = load_previous_scan(tmp_path)
    assert result is None


def test_load_previous_scan_corrupt(tmp_path: Path) -> None:
    """Test loading corrupt .imp/scan.json returns None."""
    from imp.context.staleness import load_previous_scan

    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir()
    (imp_dir / "scan.json").write_text("not valid json {{{")

    result = load_previous_scan(tmp_path)
    assert result is None
