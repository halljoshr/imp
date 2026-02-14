"""Tests for context.scanner — L1 file discovery and grouping."""

import subprocess
from datetime import UTC
from pathlib import Path

from imp.context.models import FileInfo, Language, ModuleInfo, ProjectScan
from imp.context.scanner import (
    _detect_project_type,
    detect_language,
    discover_files,
    group_into_modules,
    scan_project,
)


class TestDetectLanguage:
    """Test extension-based language detection."""

    def test_python_extension(self):
        assert detect_language(Path("script.py")) == Language.PYTHON

    def test_typescript_extensions(self):
        assert detect_language(Path("component.ts")) == Language.TYPESCRIPT
        assert detect_language(Path("component.tsx")) == Language.TYPESCRIPT

    def test_javascript_extensions(self):
        assert detect_language(Path("script.js")) == Language.JAVASCRIPT
        assert detect_language(Path("component.jsx")) == Language.JAVASCRIPT

    def test_unknown_extensions(self):
        assert detect_language(Path("README.md")) == Language.UNKNOWN
        assert detect_language(Path("data.txt")) == Language.UNKNOWN
        assert detect_language(Path("main.rs")) == Language.UNKNOWN
        assert detect_language(Path("noext")) == Language.UNKNOWN

    def test_case_insensitive(self):
        assert detect_language(Path("SCRIPT.PY")) == Language.PYTHON
        assert detect_language(Path("Component.TS")) == Language.TYPESCRIPT
        assert detect_language(Path("Script.JS")) == Language.JAVASCRIPT


class TestDiscoverFiles:
    """Test file discovery in both git and non-git directories."""

    def test_discover_non_git_directory(self, tmp_path: Path):
        """Discover files in a non-git directory with ignore filtering."""
        # Create source files
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n")
        (tmp_path / "script.js").write_text("console.log('hi');\n")

        # Create ignored directories
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"fake")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "package.js").write_text("module.exports = {};")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "activate").write_text("# venv")
        (tmp_path / ".imp").mkdir()
        (tmp_path / ".imp" / "cache.json").write_text("{}")

        # Create unknown extension (should be skipped)
        (tmp_path / "README.md").write_text("# Readme")

        files = discover_files(tmp_path)

        # Should only include recognized source files
        assert len(files) == 3

        paths = {f.path for f in files}
        assert str(tmp_path / "main.py") in paths
        assert str(tmp_path / "utils.py") in paths
        assert str(tmp_path / "script.js") in paths

        # Verify FileInfo construction
        py_file = next(f for f in files if f.path == str(tmp_path / "main.py"))
        assert py_file.language == Language.PYTHON
        assert py_file.size_bytes > 0
        assert py_file.line_count == 1

        js_file = next(f for f in files if f.path == str(tmp_path / "script.js"))
        assert js_file.language == Language.JAVASCRIPT
        assert js_file.line_count == 1

    def test_discover_git_repository(self, tmp_path: Path):
        """Discover files in a git repo using git ls-files."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        # Create and stage files
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "lib.ts").write_text("export const x = 1;\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)

        # Create unstaged file (should not be discovered)
        (tmp_path / "unstaged.py").write_text("# not tracked")

        files = discover_files(tmp_path)

        # Should only include git-tracked files
        assert len(files) == 2
        paths = {f.path for f in files}
        assert str(tmp_path / "main.py") in paths
        assert str(tmp_path / "lib.ts") in paths
        assert str(tmp_path / "unstaged.py") not in paths

    def test_discover_nested_directories(self, tmp_path: Path):
        """Discover files in nested directory structure."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helper.py").write_text("# helper")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("# test")

        files = discover_files(tmp_path)

        assert len(files) == 3
        paths = {f.path for f in files}
        assert str(tmp_path / "src" / "main.py") in paths
        assert str(tmp_path / "src" / "utils" / "helper.py") in paths
        assert str(tmp_path / "tests" / "test_main.py") in paths

    def test_discover_empty_directory(self, tmp_path: Path):
        """Empty directory returns empty list."""
        files = discover_files(tmp_path)
        assert files == []

    def test_line_count_accuracy(self, tmp_path: Path):
        """Verify line count is accurate."""
        multiline = tmp_path / "multi.py"
        multiline.write_text("line1\nline2\nline3\n")

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].line_count == 3


class TestGroupIntoModules:
    """Test grouping FileInfo objects into DirectoryModules."""

    def test_single_directory(self):
        """Files in same directory become one DirectoryModule."""
        files = [
            FileInfo(
                path="/root/main.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
            FileInfo(
                path="/root/utils.py", size_bytes=200, language=Language.PYTHON, line_count=20
            ),
        ]

        modules = group_into_modules(files)

        assert len(modules) == 1
        assert modules[0].path == "/root"
        assert len(modules[0].files) == 2
        assert modules[0].purpose is None

        # Verify ModuleInfo wrapping
        assert all(isinstance(m, ModuleInfo) for m in modules[0].files)
        assert modules[0].files[0].file_info.path == "/root/main.py"
        assert modules[0].files[1].file_info.path == "/root/utils.py"

    def test_multiple_directories(self):
        """Files in different directories become separate DirectoryModules."""
        files = [
            FileInfo(
                path="/root/src/main.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
            FileInfo(
                path="/root/src/utils.py", size_bytes=150, language=Language.PYTHON, line_count=15
            ),
            FileInfo(
                path="/root/tests/test_main.py",
                size_bytes=200,
                language=Language.PYTHON,
                line_count=20,
            ),
        ]

        modules = group_into_modules(files)

        assert len(modules) == 2
        paths = {m.path for m in modules}
        assert "/root/src" in paths
        assert "/root/tests" in paths

        src_module = next(m for m in modules if m.path == "/root/src")
        assert len(src_module.files) == 2

        tests_module = next(m for m in modules if m.path == "/root/tests")
        assert len(tests_module.files) == 1

    def test_nested_directories_maintain_structure(self):
        """Nested directories create separate modules at each level."""
        files = [
            FileInfo(path="/root/a.py", size_bytes=100, language=Language.PYTHON, line_count=10),
            FileInfo(
                path="/root/sub/b.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
            FileInfo(
                path="/root/sub/deep/c.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
        ]

        modules = group_into_modules(files)

        assert len(modules) == 3
        paths = {m.path for m in modules}
        assert "/root" in paths
        assert "/root/sub" in paths
        assert "/root/sub/deep" in paths

    def test_empty_input(self):
        """Empty input returns empty output."""
        modules = group_into_modules([])
        assert modules == []

    def test_module_info_minimal(self):
        """ModuleInfo objects are minimal (no AST data)."""
        files = [
            FileInfo(
                path="/root/main.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
        ]

        modules = group_into_modules(files)
        module_info = modules[0].files[0]

        assert module_info.file_info.path == "/root/main.py"
        assert module_info.functions == []
        assert module_info.classes == []
        assert module_info.imports == []
        assert module_info.module_docstring is None
        assert module_info.exports == []
        assert module_info.parse_error is None


class TestDetectProjectType:
    """Test project type detection from file extensions."""

    def test_python_project(self):
        files = [
            FileInfo(
                path="/root/main.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
            FileInfo(
                path="/root/utils.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
        ]
        assert _detect_project_type(files) == "python"

    def test_typescript_project(self):
        files = [
            FileInfo(
                path="/root/main.ts", size_bytes=100, language=Language.TYPESCRIPT, line_count=10
            ),
            FileInfo(
                path="/root/component.tsx",
                size_bytes=100,
                language=Language.TYPESCRIPT,
                line_count=10,
            ),
        ]
        assert _detect_project_type(files) == "typescript"

    def test_javascript_project(self):
        files = [
            FileInfo(
                path="/root/main.js", size_bytes=100, language=Language.JAVASCRIPT, line_count=10
            ),
            FileInfo(
                path="/root/component.jsx",
                size_bytes=100,
                language=Language.JAVASCRIPT,
                line_count=10,
            ),
        ]
        # JavaScript-only project should be detected as "typescript" (JS is subset)
        assert _detect_project_type(files) == "typescript"

    def test_mixed_project(self):
        files = [
            FileInfo(
                path="/root/main.py", size_bytes=100, language=Language.PYTHON, line_count=10
            ),
            FileInfo(
                path="/root/app.ts", size_bytes=100, language=Language.TYPESCRIPT, line_count=10
            ),
        ]
        assert _detect_project_type(files) == "mixed"

    def test_unknown_project(self):
        files = []
        assert _detect_project_type(files) == "unknown"

    def test_mixed_typescript_javascript(self):
        """TypeScript + JavaScript should be 'typescript' (not mixed)."""
        files = [
            FileInfo(
                path="/root/main.ts", size_bytes=100, language=Language.TYPESCRIPT, line_count=10
            ),
            FileInfo(
                path="/root/legacy.js", size_bytes=100, language=Language.JAVASCRIPT, line_count=10
            ),
        ]
        assert _detect_project_type(files) == "typescript"


class TestScanProject:
    """Test full L1 project scan integration."""

    def test_scan_python_project(self, tmp_path: Path):
        """Scan a Python project."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils").mkdir()
        (tmp_path / "utils" / "helper.py").write_text("def help():\n    pass\n")

        scan = scan_project(tmp_path)

        assert isinstance(scan, ProjectScan)
        assert scan.project_root == str(tmp_path)
        assert scan.project_type == "python"
        assert len(scan.modules) == 2
        assert scan.total_files == 2
        assert scan.total_functions == 0  # L1 doesn't parse AST
        assert scan.total_classes == 0
        assert scan.scanned_at is not None

    def test_scan_typescript_project(self, tmp_path: Path):
        """Scan a TypeScript project."""
        (tmp_path / "main.ts").write_text("export const x = 1;\n")
        (tmp_path / "component.tsx").write_text("export const C = () => null;\n")

        scan = scan_project(tmp_path)

        assert scan.project_type == "typescript"
        assert scan.total_files == 2

    def test_scan_mixed_project(self, tmp_path: Path):
        """Scan a mixed Python + TypeScript project."""
        (tmp_path / "backend.py").write_text("# backend")
        (tmp_path / "frontend.ts").write_text("// frontend")

        scan = scan_project(tmp_path)

        assert scan.project_type == "mixed"
        assert scan.total_files == 2

    def test_scan_empty_project(self, tmp_path: Path):
        """Scan an empty project."""
        scan = scan_project(tmp_path)

        assert scan.project_type == "unknown"
        assert scan.total_files == 0
        assert len(scan.modules) == 0

    def test_scan_with_ignored_files(self, tmp_path: Path):
        """Ignored files should not appear in scan."""
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"fake")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.js").write_text("// lib")

        scan = scan_project(tmp_path)

        assert scan.total_files == 1
        assert len(scan.modules) == 1
        assert scan.modules[0].path == str(tmp_path)

    def test_scanned_at_timestamp(self, tmp_path: Path):
        """Verify scanned_at is set to current time."""
        (tmp_path / "main.py").write_text("# main")

        from datetime import datetime

        before = datetime.now(UTC)
        scan = scan_project(tmp_path)
        after = datetime.now(UTC)

        assert before <= scan.scanned_at <= after

    def test_total_counts_at_l1(self, tmp_path: Path):
        """At L1, function/class counts should be 0 (no AST parsing yet)."""
        (tmp_path / "lib.py").write_text(
            "def func():\n    pass\n\nclass MyClass:\n    def method(self):\n        pass\n"
        )

        scan = scan_project(tmp_path)

        # L1 doesn't parse AST, so counts are 0
        assert scan.total_functions == 0
        assert scan.total_classes == 0

    def test_git_repo_with_deleted_tracked_file(self, tmp_path: Path):
        """Git-tracked file that no longer exists on disk is skipped."""
        # Initialize git repo and track a file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "keep.py").write_text("# keep")
        (tmp_path / "delete_me.py").write_text("# delete me")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)

        # Delete the file from disk but keep it in git index
        (tmp_path / "delete_me.py").unlink()

        files = discover_files(tmp_path)

        # Should only include files that exist on disk
        assert len(files) == 1
        assert files[0].path == str(tmp_path / "keep.py")

    def test_git_repo_with_non_source_files(self, tmp_path: Path):
        """Git-tracked files with unknown extensions should be skipped."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "README.md").write_text("# Readme")
        (tmp_path / "data.csv").write_text("a,b,c")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)

        files = discover_files(tmp_path)

        # Should only include recognized source files
        assert len(files) == 1
        assert files[0].path == str(tmp_path / "main.py")


class TestDetectProjectTypeUnknownOnly:
    """Test _detect_project_type with UNKNOWN-only files."""

    def test_unknown_language_files_only(self):
        """Files with only UNKNOWN language return 'unknown'."""
        files = [
            FileInfo(
                path="/root/data.bin", size_bytes=100, language=Language.UNKNOWN, line_count=10
            ),
        ]
        assert _detect_project_type(files) == "unknown"
