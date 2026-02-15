#!/usr/bin/env python3
"""Smoke test for context module.

This is a standalone script that validates the context module works
in the wild, not just in test harnesses.

Run with: uv run python tests/smoke/smoke_test_context.py

Exit codes:
- 0: All smoke tests passed
- 1: At least one smoke test failed
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def test_imports() -> bool:
    """Test all context modules can be imported."""
    print("Testing imports...")

    try:
        from imp.context.cli import init_command  # noqa: F401
        from imp.context.indexer import (  # noqa: F401
            generate_indexes,
            render_module_index,
            render_root_index,
            save_cache,
        )
        from imp.context.models import (  # noqa: F401
            ClassInfo,
            DirectoryModule,
            FileInfo,
            FunctionInfo,
            ImportInfo,
            Language,
            ModuleInfo,
            ProjectScan,
        )
        from imp.context.parser import parse_file, parse_python, scan_and_parse  # noqa: F401
        from imp.context.scanner import (  # noqa: F401
            detect_language,
            discover_files,
            scan_project,
        )

        print("✓ All context modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_models() -> bool:
    """Test model construction and serialization."""
    print("\nTesting models...")

    try:
        from datetime import UTC, datetime

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

        # Test Language enum
        assert Language.PYTHON == "python"
        assert Language.TYPESCRIPT == "typescript"
        assert Language.JAVASCRIPT == "javascript"
        assert Language.UNKNOWN == "unknown"

        # Test FileInfo
        file_info = FileInfo(
            path="/tmp/test.py",
            size_bytes=100,
            language=Language.PYTHON,
            line_count=10,
        )
        assert file_info.path == "/tmp/test.py"
        assert file_info.language == Language.PYTHON

        # Test FunctionInfo
        func_info = FunctionInfo(
            name="test_func",
            signature="test_func(a: int, b: str) -> None",
            line_number=5,
            docstring="A test function",
            is_method=False,
            is_async=False,
            decorators=["@staticmethod"],
        )
        assert func_info.name == "test_func"
        assert func_info.line_number == 5

        # Test ClassInfo
        class_info = ClassInfo(
            name="TestClass",
            line_number=10,
            docstring="A test class",
            bases=["BaseClass"],
            methods=[func_info],
        )
        assert class_info.name == "TestClass"
        assert len(class_info.methods) == 1

        # Test ImportInfo
        import_info = ImportInfo(
            module="typing",
            names=["List", "Dict"],
            is_from_import=True,
        )
        assert import_info.module == "typing"
        assert len(import_info.names) == 2

        # Test ModuleInfo
        module_info = ModuleInfo(
            file_info=file_info,
            functions=[func_info],
            classes=[class_info],
            imports=[import_info],
            module_docstring="Module docstring",
            exports=["TestClass", "test_func"],
        )
        assert len(module_info.functions) == 1
        assert len(module_info.classes) == 1
        assert module_info.parse_error is None

        # Test DirectoryModule
        dir_module = DirectoryModule(
            path="/tmp/src",
            files=[module_info],
            purpose="Source code",
        )
        assert dir_module.path == "/tmp/src"
        assert len(dir_module.files) == 1

        # Test ProjectScan
        project_scan = ProjectScan(
            project_root="/tmp",
            project_type="python",
            modules=[dir_module],
            total_files=1,
            total_functions=1,
            total_classes=1,
            scanned_at=datetime.now(UTC),
        )
        assert project_scan.project_type == "python"
        assert project_scan.total_files == 1

        # Test JSON serialization
        json_data = project_scan.model_dump()
        assert json_data["project_type"] == "python"
        assert json_data["total_files"] == 1

        # Test model is frozen
        try:
            file_info.path = "/tmp/other.py"  # type: ignore[misc]
            print("✗ Models should be frozen")
            return False
        except Exception:
            pass  # Expected

        print("✓ Models work correctly")
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        return False


def test_scanner() -> bool:
    """Test scanning a real temporary project."""
    print("\nTesting scanner...")

    try:
        from imp.context.scanner import detect_language, discover_files, scan_project

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create test files
            (tmp_path / "test.py").write_text("def hello(): pass")
            (tmp_path / "script.ts").write_text("function greet() {}")

            # Test detect_language
            py_lang = detect_language(tmp_path / "test.py")
            assert py_lang.value == "python"

            ts_lang = detect_language(tmp_path / "script.ts")
            assert ts_lang.value == "typescript"

            # Test discover_files
            files = discover_files(tmp_path)
            assert len(files) == 2
            assert any(f.language.value == "python" for f in files)
            assert any(f.language.value == "typescript" for f in files)

            # Test scan_project
            scan = scan_project(tmp_path)
            assert scan.project_type == "mixed"
            assert scan.total_files == 2

        print("✓ Scanner works correctly")
        return True
    except Exception as e:
        print(f"✗ Scanner test failed: {e}")
        return False


def test_parser() -> bool:
    """Test parsing real Python source."""
    print("\nTesting parser...")

    try:
        from imp.context.models import Language
        from imp.context.parser import parse_file, parse_python

        source = """
def greet(name: str) -> str:
    \"\"\"Greet someone.\"\"\"
    return f"Hello, {name}"

class Greeter:
    \"\"\"A greeter class.\"\"\"

    def say_hello(self) -> None:
        \"\"\"Say hello.\"\"\"
        print("Hello")
"""

        # Test parse_python
        module = parse_python("/tmp/test.py", source)
        assert module.parse_error is None
        assert len(module.functions) == 1
        assert module.functions[0].name == "greet"
        assert len(module.classes) == 1
        assert module.classes[0].name == "Greeter"
        assert len(module.classes[0].methods) == 1

        # Test parse_file dispatcher
        module2 = parse_file("/tmp/test.py", source, Language.PYTHON)
        assert module2.parse_error is None
        assert len(module2.functions) == 1

        # Test parse error handling
        bad_source = "def broken("
        error_module = parse_python("/tmp/bad.py", bad_source)
        assert error_module.parse_error is not None
        assert "SyntaxError" in error_module.parse_error

        print("✓ Parser works correctly")
        return True
    except Exception as e:
        print(f"✗ Parser test failed: {e}")
        return False


def test_indexer() -> bool:
    """Test generating indexes."""
    print("\nTesting indexer...")

    try:
        from imp.context.indexer import generate_indexes, render_root_index, save_cache
        from imp.context.parser import scan_and_parse

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create a Python project
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            (src_dir / "main.py").write_text("""
def main() -> None:
    \"\"\"Main function.\"\"\"
    print("Hello")
""")

            # Scan and parse
            scan = scan_and_parse(tmp_path)

            # Test render_root_index
            root_md = render_root_index(scan)
            assert isinstance(root_md, str)
            assert len(root_md) > 0

            # Test generate_indexes
            generate_indexes(scan, tmp_path)
            assert (tmp_path / ".index.md").exists()
            assert (src_dir / ".index.md").exists()

            # Test save_cache
            save_cache(scan, tmp_path)
            cache_file = tmp_path / ".imp" / "scan.json"
            assert cache_file.exists()

            import json

            cache_data = json.loads(cache_file.read_text())
            assert cache_data["project_type"] == "python"

        print("✓ Indexer works correctly")
        return True
    except Exception as e:
        print(f"✗ Indexer test failed: {e}")
        return False


def test_cli() -> bool:
    """Test CLI command."""
    print("\nTesting CLI...")

    try:
        from imp.context.cli import init_command

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create a simple project
            (tmp_path / "test.py").write_text("def foo(): pass")

            # Run init_command
            exit_code = init_command(root=tmp_path, format="human")
            assert exit_code == 0

            # Verify artifacts
            assert (tmp_path / ".index.md").exists()
            assert (tmp_path / ".imp" / "scan.json").exists()

        print("✓ CLI command works correctly")
        return True
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False


def test_real_project() -> bool:
    """Test on the actual Imp project."""
    print("\nTesting on real Imp project...")

    try:
        from imp.context.parser import scan_and_parse

        # Find the imp project root
        imp_root = Path(__file__).parent.parent.parent
        assert (imp_root / "pyproject.toml").exists()

        # Scan the Imp project
        scan = scan_and_parse(imp_root)

        # Verify scan results
        assert scan.project_type == "python"
        assert scan.total_files > 0
        assert scan.total_functions > 0

        print("✓ Real project scan works")
        print(f"  Scanned {scan.total_files} files")
        print(f"  Found {scan.total_functions} functions")
        print(f"  Found {scan.total_classes} classes")
        return True
    except Exception as e:
        print(f"✗ Real project test failed: {e}")
        return False


def test_l3_imports() -> bool:
    """Test L3 module imports (summarizer, staleness, summary cache)."""
    print("\nTesting L3 imports...")

    try:
        from imp.context.staleness import (  # noqa: F401
            StaleModule,
            detect_stale_modules,
            load_previous_scan,
        )
        from imp.context.summarizer import (  # noqa: F401
            InvokeFn,
            build_prompt,
            summarize_module,
            summarize_project,
        )
        from imp.context.summary_cache import (  # noqa: F401
            SummaryEntry,
            load_summaries,
            save_summaries,
        )

        print("✓ All L3 modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ L3 import error: {e}")
        return False


def test_l3_models() -> bool:
    """Test L3 model construction and serialization."""
    print("\nTesting L3 models...")

    try:
        from datetime import UTC, datetime

        from imp.context.staleness import StaleModule
        from imp.context.summary_cache import SummaryEntry

        # Test SummaryEntry
        entry = SummaryEntry(
            purpose="Handles authentication.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        )
        assert entry.purpose == "Handles authentication."
        json_data = entry.model_dump()
        assert json_data["purpose"] == "Handles authentication."

        # Test StaleModule
        stale = StaleModule(
            module_path="src/",
            reason="files_modified",
            changed_files=["src/main.py"],
        )
        assert stale.module_path == "src/"
        assert stale.reason == "files_modified"

        print("✓ L3 models work correctly")
        return True
    except Exception as e:
        print(f"✗ L3 model test failed: {e}")
        return False


def test_summary_cache_round_trip() -> bool:
    """Test summary cache save/load round-trip."""
    print("\nTesting summary cache round-trip...")

    try:
        from datetime import UTC, datetime

        from imp.context.summary_cache import SummaryEntry, load_summaries, save_summaries

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            summaries = {
                "src/": SummaryEntry(
                    purpose="Source code.",
                    summarized_at=datetime.now(UTC),
                    model_used="test-model",
                ),
            }
            save_summaries(summaries, tmp_path)
            loaded = load_summaries(tmp_path)

            assert len(loaded) == 1
            assert loaded["src/"].purpose == "Source code."

        print("✓ Summary cache round-trip works")
        return True
    except Exception as e:
        print(f"✗ Summary cache test failed: {e}")
        return False


def main() -> int:
    """Run all smoke tests."""
    print("=" * 60)
    print("Context Module Smoke Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_models,
        test_scanner,
        test_parser,
        test_indexer,
        test_cli,
        test_real_project,
        test_l3_imports,
        test_l3_models,
        test_summary_cache_round_trip,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All smoke tests passed!")
        return 0
    else:
        print("\n❌ Some smoke tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
