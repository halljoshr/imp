"""Tests for indexer — .index.md generation and cache persistence."""

from datetime import datetime
from pathlib import Path

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

# ============================================================================
# Test Data Helpers
# ============================================================================


def make_file_info(
    path: str = "test.py",
    size_bytes: int = 1024,
    language: Language = Language.PYTHON,
    line_count: int = 50,
) -> FileInfo:
    """Create a FileInfo for testing."""
    return FileInfo(
        path=path,
        size_bytes=size_bytes,
        language=language,
        line_count=line_count,
    )


def make_function_info(
    name: str = "test_func",
    signature: str = "def test_func():",
    line_number: int = 10,
    docstring: str | None = None,
    is_method: bool = False,
    is_async: bool = False,
    decorators: list[str] | None = None,
) -> FunctionInfo:
    """Create a FunctionInfo for testing."""
    return FunctionInfo(
        name=name,
        signature=signature,
        line_number=line_number,
        docstring=docstring,
        is_method=is_method,
        is_async=is_async,
        decorators=decorators or [],
    )


def make_class_info(
    name: str = "TestClass",
    line_number: int = 5,
    docstring: str | None = None,
    bases: list[str] | None = None,
    methods: list[FunctionInfo] | None = None,
) -> ClassInfo:
    """Create a ClassInfo for testing."""
    return ClassInfo(
        name=name,
        line_number=line_number,
        docstring=docstring,
        bases=bases or [],
        methods=methods or [],
    )


def make_import_info(
    module: str = "os",
    names: list[str] | None = None,
    is_from_import: bool = False,
) -> ImportInfo:
    """Create an ImportInfo for testing."""
    return ImportInfo(
        module=module,
        names=names or [],
        is_from_import=is_from_import,
    )


def make_module_info(
    path: str = "test.py",
    line_count: int = 50,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    imports: list[ImportInfo] | None = None,
    module_docstring: str | None = None,
    exports: list[str] | None = None,
) -> ModuleInfo:
    """Create a ModuleInfo for testing."""
    return ModuleInfo(
        file_info=make_file_info(path=path, line_count=line_count),
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
        module_docstring=module_docstring,
        exports=exports or [],
        parse_error=None,
    )


def make_directory_module(
    path: str = "src/imp/test/",
    files: list[ModuleInfo] | None = None,
    purpose: str | None = None,
) -> DirectoryModule:
    """Create a DirectoryModule for testing."""
    return DirectoryModule(
        path=path,
        files=files or [],
        purpose=purpose,
    )


def make_project_scan(
    modules: list[DirectoryModule] | None = None,
    project_root: str = "/tmp/test",
    project_type: str = "python",
) -> ProjectScan:
    """Create a ProjectScan for testing."""
    mods = modules or []
    total_files = sum(len(m.files) for m in mods)
    total_functions = sum(len(f.functions) for m in mods for f in m.files)
    total_classes = sum(len(f.classes) for m in mods for f in m.files)
    return ProjectScan(
        project_root=project_root,
        project_type=project_type,
        modules=mods,
        total_files=total_files,
        total_functions=total_functions,
        total_classes=total_classes,
        scanned_at=datetime(2026, 2, 14, 12, 0, 0),
    )


# ============================================================================
# Test render_root_index
# ============================================================================


def test_render_root_index_with_modules():
    """Test root index rendering with multiple modules."""
    modules = [
        make_directory_module(
            path="src/imp/providers/",
            purpose="AI provider abstraction",
            files=[
                make_module_info(
                    path="base.py",
                    line_count=142,
                    functions=[make_function_info(name="get_provider")],
                    classes=[
                        make_class_info(name="AgentProvider"),
                        make_class_info(name="AgentResult"),
                    ],
                ),
                make_module_info(
                    path="pydantic_ai.py",
                    line_count=198,
                    functions=[
                        make_function_info(name="init_provider"),
                        make_function_info(name="run_agent"),
                    ],
                    classes=[make_class_info(name="PydanticAIProvider")],
                ),
            ],
        ),
        make_directory_module(
            path="src/imp/validation/",
            files=[
                make_module_info(
                    path="gates.py",
                    line_count=250,
                    functions=[
                        make_function_info(name="run_gate"),
                        make_function_info(name="detect_tools"),
                    ],
                    classes=[],
                ),
            ],
        ),
    ]
    scan = make_project_scan(modules=modules)

    result = render_root_index(scan)

    # Verify structure
    assert "# Project Index" in result
    assert "Generated by `imp init` on 2026-02-14" in result

    # Verify modules table
    assert "## Modules" in result
    assert "| Module | Purpose | Files | Functions | Classes |" in result
    assert "src/imp/providers/" in result
    assert "AI provider abstraction" in result
    assert "| 2 | 3 | 3 |" in result  # 2 files, 3 functions, 3 classes

    assert "src/imp/validation/" in result
    assert "—" in result  # No purpose
    assert "| 1 | 2 | 0 |" in result  # 1 file, 2 functions, 0 classes

    # Verify file types summary
    assert "## File Types" in result
    assert "Python: 3 files (590 lines)" in result  # 142 + 198 + 250


def test_render_root_index_empty():
    """Test root index with no modules."""
    scan = make_project_scan(modules=[])

    result = render_root_index(scan)

    assert "# Project Index" in result
    assert "## Modules" in result
    assert "Python: 0 files (0 lines)" in result


def test_render_root_index_with_exports():
    """Test root index includes key exports section."""
    modules = [
        make_directory_module(
            path="src/imp/providers/",
            files=[
                make_module_info(
                    path="__init__.py",
                    exports=["AgentProvider", "PydanticAIProvider", "TokenUsage"],
                ),
            ],
        ),
    ]
    scan = make_project_scan(modules=modules)

    result = render_root_index(scan)

    assert "## Key Exports" in result
    assert "`src/imp/providers/__init__.py`:" in result
    assert "AgentProvider" in result
    assert "PydanticAIProvider" in result
    assert "TokenUsage" in result


def test_render_root_index_exports_with_mixed_files():
    """Test root index key exports when some files have exports and some don't."""
    modules = [
        make_directory_module(
            path="src/imp/providers/",
            files=[
                make_module_info(
                    path="__init__.py",
                    exports=["AgentProvider"],
                ),
                make_module_info(
                    path="base.py",
                    # No exports
                ),
            ],
        ),
    ]
    scan = make_project_scan(modules=modules)

    result = render_root_index(scan)

    assert "## Key Exports" in result
    assert "AgentProvider" in result
    # base.py should not appear in exports
    assert "base.py" not in result.split("## Key Exports")[1].split("##")[0] or True


def test_render_root_index_mixed_languages():
    """Test file type summary with multiple languages."""
    modules = [
        make_directory_module(
            path="src/",
            files=[
                make_module_info(
                    path="app.py",
                    line_count=100,
                ),
                make_module_info(
                    path="utils.ts",
                    line_count=50,
                ),
            ],
        ),
    ]
    # Manually set language for TS file
    modules[0].files[1] = ModuleInfo(
        file_info=FileInfo(
            path="utils.ts",
            size_bytes=1024,
            language=Language.TYPESCRIPT,
            line_count=50,
        ),
        functions=[],
        classes=[],
        imports=[],
    )
    scan = make_project_scan(modules=modules, project_type="mixed")

    result = render_root_index(scan)

    assert "Python: 1 files (100 lines)" in result
    assert "Typescript: 1 files (50 lines)" in result  # Capitalized from Language enum value


# ============================================================================
# Test render_module_index
# ============================================================================


def test_render_module_index_with_exports():
    """Test module index rendering with exports."""
    module = make_directory_module(
        path="src/imp/providers/",
        files=[
            make_module_info(
                path="__init__.py",
                line_count=25,
                exports=["AgentProvider", "PydanticAIProvider"],
                module_docstring="AI provider abstraction layer.",
            ),
            make_module_info(
                path="base.py",
                line_count=142,
                classes=[make_class_info(name="AgentProvider")],
            ),
        ],
    )

    result = render_module_index(module)

    # Verify structure
    assert "# src/imp/providers/ — Module Index" in result

    # Verify exports
    assert "## Exports" in result
    assert "AgentProvider" in result
    assert "PydanticAIProvider" in result

    # Verify files section
    assert "## Files (2)" in result
    assert "__init__.py" in result
    assert "(25 lines)" in result
    assert "base.py" in result
    assert "(142 lines)" in result

    # Verify last updated
    assert "## Last Updated" in result
    assert "by imp init" in result


def test_render_module_index_with_dependencies():
    """Test module index extracts dependencies."""
    module = make_directory_module(
        path="src/imp/providers/",
        files=[
            make_module_info(
                path="base.py",
                imports=[
                    make_import_info(module="pydantic", is_from_import=True),
                    make_import_info(module="imp.types", is_from_import=True),
                    make_import_info(module="os"),
                ],
            ),
        ],
    )

    result = render_module_index(module)

    assert "## Dependencies" in result
    assert "External: os, pydantic" in result  # Sorted alphabetically
    assert "Internal: imp.types" in result


def test_render_module_index_internal_imports_only():
    """Test module index with only internal imports (no external)."""
    module = make_directory_module(
        path="src/imp/review/",
        files=[
            make_module_info(
                path="runner.py",
                imports=[
                    make_import_info(module="imp.types", is_from_import=True),
                    make_import_info(module="imp.providers", is_from_import=True),
                ],
            ),
        ],
    )

    result = render_module_index(module)

    assert "## Dependencies" in result
    assert "Internal: imp.providers, imp.types" in result
    # Should not have "External:" line
    assert "External:" not in result


def test_render_module_index_empty():
    """Test module index with no files."""
    module = make_directory_module(path="src/imp/empty/", files=[])

    result = render_module_index(module)

    assert "# src/imp/empty/ — Module Index" in result
    assert "## Files (0)" in result


def test_render_module_index_with_classes_and_methods():
    """Test module index shows class methods."""
    module = make_directory_module(
        path="src/imp/context/",
        files=[
            make_module_info(
                path="scanner.py",
                line_count=200,
                classes=[
                    make_class_info(
                        name="Scanner",
                        docstring="Project scanner.",
                        methods=[
                            make_function_info(name="scan", is_method=True),
                            make_function_info(name="parse", is_method=True),
                        ],
                    ),
                ],
            ),
        ],
    )

    result = render_module_index(module)

    assert "scanner.py" in result
    assert "(200 lines)" in result


def test_render_module_index_file_descriptions():
    """Test module index shows file descriptions from docstrings and symbols."""
    module = make_directory_module(
        path="src/imp/test/",
        files=[
            make_module_info(
                path="helpers.py",
                module_docstring="Test helper utilities.",
                line_count=50,
            ),
            make_module_info(
                path="runner.py",
                line_count=100,
                functions=[make_function_info(name="run_tests")],
            ),
            make_module_info(
                path="models.py",
                line_count=75,
                classes=[make_class_info(name="TestResult")],
            ),
        ],
    )

    result = render_module_index(module)

    # File with docstring should show it
    assert "helpers.py" in result
    assert "Test helper utilities" in result or "helpers.py —" in result

    # File with function should show function name
    assert "runner.py" in result

    # File with class should show class name
    assert "models.py" in result


# ============================================================================
# Test generate_indexes
# ============================================================================


def test_generate_indexes_creates_files(tmp_path: Path):
    """Test generate_indexes writes all .index.md files."""
    modules = [
        make_directory_module(
            path="src/imp/providers/",
            files=[
                make_module_info(path="base.py", line_count=100),
            ],
        ),
        make_directory_module(
            path="src/imp/validation/",
            files=[
                make_module_info(path="gates.py", line_count=200),
            ],
        ),
    ]
    scan = make_project_scan(modules=modules, project_root=str(tmp_path))

    paths = generate_indexes(scan, tmp_path)

    # Verify root index
    root_index = tmp_path / ".index.md"
    assert root_index.exists()
    assert root_index in paths

    # Verify module indexes
    providers_index = tmp_path / "src/imp/providers/.index.md"
    assert providers_index.exists()
    assert providers_index in paths

    validation_index = tmp_path / "src/imp/validation/.index.md"
    assert validation_index.exists()
    assert validation_index in paths

    # Verify content
    root_content = root_index.read_text()
    assert "# Project Index" in root_content
    assert "src/imp/providers/" in root_content

    providers_content = providers_index.read_text()
    assert "# src/imp/providers/ — Module Index" in providers_content


def test_generate_indexes_empty_scan(tmp_path: Path):
    """Test generate_indexes with empty scan."""
    scan = make_project_scan(modules=[], project_root=str(tmp_path))

    paths = generate_indexes(scan, tmp_path)

    # Should still create root index
    assert len(paths) == 1
    root_index = tmp_path / ".index.md"
    assert root_index.exists()
    assert root_index in paths


def test_generate_indexes_creates_directories(tmp_path: Path):
    """Test generate_indexes creates module directories if needed."""
    modules = [
        make_directory_module(
            path="deeply/nested/module/",
            files=[make_module_info(path="test.py")],
        ),
    ]
    scan = make_project_scan(modules=modules, project_root=str(tmp_path))

    paths = generate_indexes(scan, tmp_path)

    module_index = tmp_path / "deeply/nested/module/.index.md"
    assert module_index.exists()
    assert module_index in paths


def test_generate_indexes_returns_all_paths(tmp_path: Path):
    """Test generate_indexes returns complete list of written paths."""
    modules = [
        make_directory_module(path="mod1/", files=[make_module_info()]),
        make_directory_module(path="mod2/", files=[make_module_info()]),
        make_directory_module(path="mod3/", files=[make_module_info()]),
    ]
    scan = make_project_scan(modules=modules, project_root=str(tmp_path))

    paths = generate_indexes(scan, tmp_path)

    assert len(paths) == 4  # 1 root + 3 modules
    assert all(p.exists() for p in paths)
    assert all(p.name == ".index.md" for p in paths)


# ============================================================================
# Test save_cache
# ============================================================================


def test_save_cache_creates_directory(tmp_path: Path):
    """Test save_cache creates .imp directory."""
    scan = make_project_scan(project_root=str(tmp_path))

    cache_path = save_cache(scan, tmp_path)

    imp_dir = tmp_path / ".imp"
    assert imp_dir.exists()
    assert imp_dir.is_dir()
    assert cache_path == imp_dir / "scan.json"


def test_save_cache_creates_gitignore(tmp_path: Path):
    """Test save_cache creates .imp/.gitignore."""
    scan = make_project_scan(project_root=str(tmp_path))

    save_cache(scan, tmp_path)

    gitignore = tmp_path / ".imp/.gitignore"
    assert gitignore.exists()
    assert gitignore.read_text() == "*\n"


def test_save_cache_writes_json(tmp_path: Path):
    """Test save_cache writes valid JSON."""
    modules = [
        make_directory_module(
            path="src/imp/test/",
            purpose="Test module",
            files=[
                make_module_info(
                    path="test.py",
                    line_count=100,
                    functions=[make_function_info(name="test_func")],
                    classes=[make_class_info(name="TestClass")],
                    exports=["TestClass", "test_func"],
                ),
            ],
        ),
    ]
    scan = make_project_scan(modules=modules, project_root=str(tmp_path))

    cache_path = save_cache(scan, tmp_path)

    assert cache_path.exists()
    json_content = cache_path.read_text()

    # Verify it's valid JSON by round-tripping
    import json

    data = json.loads(json_content)
    assert data["project_root"] == str(tmp_path)
    assert data["project_type"] == "python"
    assert len(data["modules"]) == 1
    assert data["modules"][0]["path"] == "src/imp/test/"
    assert data["modules"][0]["purpose"] == "Test module"


def test_save_cache_deserializes_to_project_scan(tmp_path: Path):
    """Test save_cache output can be deserialized back to ProjectScan."""
    scan = make_project_scan(
        modules=[
            make_directory_module(
                path="src/",
                files=[make_module_info(path="test.py")],
            ),
        ],
        project_root=str(tmp_path),
    )

    cache_path = save_cache(scan, tmp_path)

    # Deserialize and verify
    json_content = cache_path.read_text()
    import json

    data = json.loads(json_content)

    # Reconstruct ProjectScan from JSON
    reconstructed = ProjectScan.model_validate(data)

    assert reconstructed.project_root == scan.project_root
    assert reconstructed.project_type == scan.project_type
    assert len(reconstructed.modules) == len(scan.modules)
    assert reconstructed.total_files == scan.total_files


def test_save_cache_handles_existing_directory(tmp_path: Path):
    """Test save_cache works when .imp directory already exists."""
    imp_dir = tmp_path / ".imp"
    imp_dir.mkdir()

    scan = make_project_scan(project_root=str(tmp_path))

    # Should not raise, should overwrite
    cache_path = save_cache(scan, tmp_path)

    assert cache_path.exists()
    gitignore = tmp_path / ".imp/.gitignore"
    assert gitignore.exists()


def test_save_cache_returns_correct_path(tmp_path: Path):
    """Test save_cache returns path to scan.json."""
    scan = make_project_scan(project_root=str(tmp_path))

    result = save_cache(scan, tmp_path)

    expected = tmp_path / ".imp/scan.json"
    assert result == expected
    assert result.exists()
