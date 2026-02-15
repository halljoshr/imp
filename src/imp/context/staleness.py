"""Staleness detection — identify modules that need re-scanning.

Compares two ProjectScan snapshots to find new, deleted, and modified modules.
Uses file lists and sizes/line counts for change detection (no filesystem access).
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from imp.context.models import DirectoryModule, ProjectScan


class StaleModule(BaseModel):
    """A module whose index is out of date."""

    module_path: str
    reason: (
        str  # "module_added", "module_deleted", "files_added", "files_deleted", "files_modified"
    )
    changed_files: list[str]

    model_config = ConfigDict(frozen=True)


def _file_signature(module: DirectoryModule) -> dict[str, tuple[int, int]]:
    """Build a signature map: file_path -> (size_bytes, line_count)."""
    return {
        f.file_info.path: (f.file_info.size_bytes, f.file_info.line_count) for f in module.files
    }


def detect_stale_modules(
    current_scan: ProjectScan,
    previous_scan: ProjectScan,
) -> list[StaleModule]:
    """Compare two scans, return modules that changed.

    Detects:
    - New modules (in current but not previous)
    - Deleted modules (in previous but not current)
    - Modules with added/deleted/modified files

    Args:
        current_scan: Latest scan result
        previous_scan: Previous scan result (from cache)

    Returns:
        List of StaleModule with change reasons
    """
    stale: list[StaleModule] = []

    current_paths = {m.path for m in current_scan.modules}
    previous_paths = {m.path for m in previous_scan.modules}
    previous_map = {m.path: m for m in previous_scan.modules}
    current_map = {m.path: m for m in current_scan.modules}

    # New modules
    for path in sorted(current_paths - previous_paths):
        module = current_map[path]
        stale.append(
            StaleModule(
                module_path=path,
                reason="module_added",
                changed_files=[f.file_info.path for f in module.files],
            )
        )

    # Deleted modules
    for path in sorted(previous_paths - current_paths):
        module = previous_map[path]
        stale.append(
            StaleModule(
                module_path=path,
                reason="module_deleted",
                changed_files=[f.file_info.path for f in module.files],
            )
        )

    # Shared modules — check for file changes
    for path in sorted(current_paths & previous_paths):
        current_sigs = _file_signature(current_map[path])
        previous_sigs = _file_signature(previous_map[path])

        current_files = set(current_sigs.keys())
        previous_files = set(previous_sigs.keys())

        added = current_files - previous_files
        if added:
            stale.append(
                StaleModule(
                    module_path=path,
                    reason="files_added",
                    changed_files=sorted(added),
                )
            )
            continue

        deleted = previous_files - current_files
        if deleted:
            stale.append(
                StaleModule(
                    module_path=path,
                    reason="files_deleted",
                    changed_files=sorted(deleted),
                )
            )
            continue

        # Check for modifications (size or line count changed)
        modified = [f for f in current_files if current_sigs[f] != previous_sigs[f]]
        if modified:
            stale.append(
                StaleModule(
                    module_path=path,
                    reason="files_modified",
                    changed_files=sorted(modified),
                )
            )

    return stale


def load_previous_scan(project_root: Path) -> ProjectScan | None:
    """Load .imp/scan.json if it exists.

    Returns None if file doesn't exist or is corrupt.

    Args:
        project_root: Root directory of the project

    Returns:
        Previous ProjectScan or None
    """
    scan_path = project_root / ".imp" / "scan.json"
    if not scan_path.exists():
        return None

    try:
        data = json.loads(scan_path.read_text())
        return ProjectScan.model_validate(data)
    except (json.JSONDecodeError, Exception):
        return None
