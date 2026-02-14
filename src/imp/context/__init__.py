"""Imp context — context window management and project understanding."""

from imp.context.cli import init_command
from imp.context.indexer import (
    generate_indexes,
    render_module_index,
    render_root_index,
    save_cache,
)
from imp.context.models import (
    ClassInfo,
    DirectoryModule,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ProjectScan,
)
from imp.context.parser import (
    parse_file,
    parse_python,
    parse_typescript,
    scan_and_parse,
)
from imp.context.scanner import (
    detect_language,
    discover_files,
    scan_project,
)

__all__ = [
    "ClassInfo",
    "DirectoryModule",
    "FileInfo",
    "FunctionInfo",
    "ImportInfo",
    "Language",
    "ModuleInfo",
    "ProjectScan",
    "detect_language",
    "discover_files",
    "generate_indexes",
    "init_command",
    "parse_file",
    "parse_python",
    "parse_typescript",
    "render_module_index",
    "render_root_index",
    "save_cache",
    "scan_and_parse",
    "scan_project",
]
