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
from imp.context.staleness import (
    StaleModule,
    detect_stale_modules,
    load_previous_scan,
)
from imp.context.summarizer import (
    InvokeFn,
    build_prompt,
    summarize_module,
    summarize_project,
)
from imp.context.summary_cache import (
    SummaryEntry,
    load_summaries,
    save_summaries,
)

__all__ = [
    "ClassInfo",
    "DirectoryModule",
    "FileInfo",
    "FunctionInfo",
    "ImportInfo",
    "InvokeFn",
    "Language",
    "ModuleInfo",
    "ProjectScan",
    "StaleModule",
    "SummaryEntry",
    "build_prompt",
    "detect_language",
    "detect_stale_modules",
    "discover_files",
    "generate_indexes",
    "init_command",
    "load_previous_scan",
    "load_summaries",
    "parse_file",
    "parse_python",
    "parse_typescript",
    "render_module_index",
    "render_root_index",
    "save_cache",
    "save_summaries",
    "scan_and_parse",
    "scan_project",
    "summarize_module",
    "summarize_project",
]
