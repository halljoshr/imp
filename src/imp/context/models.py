"""Context models — L0 types for project understanding.

L0 constraint: Only import from pydantic, datetime, stdlib.
NO imports from other imp.* modules.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Language(StrEnum):
    """Programming language detected for a source file."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    UNKNOWN = "unknown"


class FileInfo(BaseModel):
    """L1: Static information about a source file."""

    path: str
    size_bytes: int
    language: Language
    line_count: int

    model_config = ConfigDict(frozen=True)


class FunctionInfo(BaseModel):
    """A function/method extracted from AST."""

    name: str
    signature: str
    line_number: int
    docstring: str | None = None
    is_method: bool = False
    is_async: bool = False
    decorators: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ClassInfo(BaseModel):
    """A class extracted from AST."""

    name: str
    line_number: int
    docstring: str | None = None
    bases: list[str] = Field(default_factory=list)
    methods: list[FunctionInfo] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ImportInfo(BaseModel):
    """An import statement."""

    module: str
    names: list[str] = Field(default_factory=list)
    is_from_import: bool = False

    model_config = ConfigDict(frozen=True)


class ModuleInfo(BaseModel):
    """Complete L2 analysis of a single source file."""

    file_info: FileInfo
    functions: list[FunctionInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    module_docstring: str | None = None
    exports: list[str] = Field(default_factory=list)
    parse_error: str | None = None

    model_config = ConfigDict(frozen=True)


class DirectoryModule(BaseModel):
    """A group of source files in a directory."""

    path: str
    files: list[ModuleInfo]
    purpose: str | None = None

    model_config = ConfigDict(frozen=True)


class ProjectScan(BaseModel):
    """Complete L1+L2 scan result."""

    project_root: str
    project_type: str  # "python", "typescript", "mixed", "unknown"
    modules: list[DirectoryModule]
    total_files: int
    total_functions: int
    total_classes: int
    scanned_at: datetime

    model_config = ConfigDict(frozen=True)
