"""Context scanner — L1 file discovery and project scanning.

L1 constraint: Only imports from stdlib, imp.context.models.
Discovers source files and groups them into DirectoryModules.
No AST parsing at this level.
"""

import os
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from imp.context.models import DirectoryModule, FileInfo, Language, ModuleInfo, ProjectScan

# Common directories to ignore in non-git projects
IGNORE_DIRS = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".imp",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pypackages__",
    "egg-info",
    ".egg-info",
}


def detect_language(path: Path) -> Language:
    """Classify file by extension.

    Args:
        path: File path to classify

    Returns:
        Language enum value based on extension
    """
    ext = path.suffix.lower()

    if ext == ".py":
        return Language.PYTHON
    elif ext in {".ts", ".tsx"}:
        return Language.TYPESCRIPT
    elif ext in {".js", ".jsx"}:
        return Language.JAVASCRIPT
    else:
        return Language.UNKNOWN


def discover_files(root: Path) -> list[FileInfo]:
    """Discover source files in a project.

    Uses `git ls-files` if in a git repo, falls back to os.walk
    with hardcoded ignore list for non-git directories.
    Only include files with recognized language extensions.

    Args:
        root: Project root directory

    Returns:
        List of FileInfo objects for all discovered source files
    """
    # Check if this is a git repo
    is_git_repo = False
    try:
        git_check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        is_git_repo = git_check.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):  # pragma: no cover
        is_git_repo = False

    files: list[FileInfo] = []

    if is_git_repo:
        # Use git ls-files for tracked files
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [root / p for p in result.stdout.strip().split("\n") if p]

        for path in paths:
            if not path.is_file():
                continue

            lang = detect_language(path)
            if lang == Language.UNKNOWN:
                continue

            size_bytes = path.stat().st_size
            line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())

            files.append(
                FileInfo(
                    path=str(path),
                    size_bytes=size_bytes,
                    language=lang,
                    line_count=line_count,
                )
            )
    else:
        # Use os.walk with ignore list
        for dirpath, dirnames, filenames in os.walk(root):
            # Filter out ignored directories
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

            for filename in filenames:
                path = Path(dirpath) / filename
                lang = detect_language(path)

                if lang == Language.UNKNOWN:
                    continue

                size_bytes = path.stat().st_size
                line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())

                files.append(
                    FileInfo(
                        path=str(path),
                        size_bytes=size_bytes,
                        language=lang,
                        line_count=line_count,
                    )
                )

    return files


def group_into_modules(files: list[FileInfo]) -> list[DirectoryModule]:
    """Group files by directory into DirectoryModules.

    Each directory containing source files becomes one DirectoryModule.
    The files list in DirectoryModule contains ModuleInfo objects with
    just file_info populated (no AST data — that's the parser's job).

    Args:
        files: List of FileInfo objects to group

    Returns:
        List of DirectoryModule objects, one per directory
    """
    if not files:
        return []

    # Group files by directory
    dir_files: dict[str, list[FileInfo]] = defaultdict(list)
    for file_info in files:
        directory = str(Path(file_info.path).parent)
        dir_files[directory].append(file_info)

    # Create DirectoryModule for each directory
    modules: list[DirectoryModule] = []
    for directory, dir_file_list in sorted(dir_files.items()):
        # Wrap each FileInfo in a minimal ModuleInfo (no AST data)
        module_infos = [ModuleInfo(file_info=fi) for fi in dir_file_list]

        modules.append(
            DirectoryModule(
                path=directory,
                files=module_infos,
                purpose=None,  # L1 doesn't infer purpose yet
            )
        )

    return modules


def _detect_project_type(files: list[FileInfo]) -> str:
    """Detect project type from file extensions.

    Returns "python", "typescript", "mixed", or "unknown".

    Args:
        files: List of FileInfo objects to analyze

    Returns:
        Project type string
    """
    if not files:
        return "unknown"

    languages = {f.language for f in files}

    # JavaScript is a subset of TypeScript, so JS-only or TS+JS = "typescript"
    has_python = Language.PYTHON in languages
    has_ts_or_js = Language.TYPESCRIPT in languages or Language.JAVASCRIPT in languages

    if has_python and has_ts_or_js:
        return "mixed"
    elif has_python:
        return "python"
    elif has_ts_or_js:
        return "typescript"
    else:
        return "unknown"


def scan_project(root: Path) -> ProjectScan:
    """Main L1 entry point. Discovers files, groups into modules, returns ProjectScan.

    Args:
        root: Project root directory

    Returns:
        ProjectScan object with L1 analysis results
    """
    files = discover_files(root)
    modules = group_into_modules(files)
    project_type = _detect_project_type(files)

    return ProjectScan(
        project_root=str(root),
        project_type=project_type,
        modules=modules,
        total_files=len(files),
        total_functions=0,  # L1 doesn't parse AST yet
        total_classes=0,  # L1 doesn't parse AST yet
        scanned_at=datetime.now(UTC),
    )
