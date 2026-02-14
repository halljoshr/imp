"""Integration tests for context module — full pipeline tests."""

import json
from pathlib import Path


def test_full_pipeline_python_project(tmp_path: Path) -> None:
    """Test full L1+L2+indexing pipeline on a Python project."""
    from imp.context.indexer import generate_indexes, save_cache
    from imp.context.parser import scan_and_parse

    # Create a multi-file Python project
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create module with functions and classes
    (src_dir / "core.py").write_text("""
def hello() -> str:
    \"\"\"Say hello.\"\"\"
    return "Hello"

class Greeter:
    \"\"\"A greeter class.\"\"\"

    def greet(self, name: str) -> str:
        \"\"\"Greet someone.\"\"\"
        return f"Hello, {name}"
""")

    # Create another module
    (src_dir / "utils.py").write_text("""
from typing import List

def process_items(items: List[str]) -> None:
    \"\"\"Process items.\"\"\"
    for item in items:
        print(item)
""")

    # Scan and parse (L1+L2)
    scan_result = scan_and_parse(tmp_path)

    # Verify scan result
    assert scan_result.project_root == str(tmp_path)
    assert scan_result.project_type == "python"
    assert scan_result.total_files == 2
    assert scan_result.total_functions >= 2  # hello, process_items
    assert scan_result.total_classes >= 1  # Greeter

    # Generate indexes
    generate_indexes(scan_result, tmp_path)

    # Verify root .index.md exists
    root_index = tmp_path / ".index.md"
    assert root_index.exists()
    content = root_index.read_text()
    # Root index should list modules with stats
    assert "src" in content or str(src_dir) in content
    assert "2" in content  # 2 files or 2 functions

    # Verify module .index.md exists
    module_index = src_dir / ".index.md"
    assert module_index.exists()
    module_content = module_index.read_text()

    # Should mention the files
    assert "core.py" in module_content or "utils.py" in module_content

    # Save cache
    save_cache(scan_result, tmp_path)
    cache_file = tmp_path / ".imp" / "scan.json"
    assert cache_file.exists()

    # Verify cache is valid JSON and contains expected data
    cache_data = json.loads(cache_file.read_text())
    assert cache_data["project_type"] == "python"
    assert cache_data["total_files"] == 2


def test_full_pipeline_empty_project(tmp_path: Path) -> None:
    """Test full pipeline on an empty project."""
    from imp.context.indexer import generate_indexes
    from imp.context.parser import scan_and_parse

    # Empty directory
    scan_result = scan_and_parse(tmp_path)

    # Should succeed with zero files
    assert scan_result.total_files == 0
    assert scan_result.total_functions == 0
    assert scan_result.total_classes == 0

    # Generate indexes (should create root index even if empty)
    generate_indexes(scan_result, tmp_path)

    # Verify root .index.md exists
    root_index = tmp_path / ".index.md"
    assert root_index.exists()

    # Content should indicate empty project or have empty tables
    content = root_index.read_text()
    assert len(content) > 0


def test_round_trip_serialization(tmp_path: Path) -> None:
    """Test that scan results can be saved and loaded."""
    from imp.context.indexer import save_cache
    from imp.context.models import ProjectScan
    from imp.context.parser import scan_and_parse

    # Create a simple Python project
    (tmp_path / "test.py").write_text("def foo(): pass")

    # Scan and parse
    original_scan = scan_and_parse(tmp_path)

    # Save to cache
    save_cache(original_scan, tmp_path)

    # Load from JSON
    cache_file = tmp_path / ".imp" / "scan.json"
    cache_json = json.loads(cache_file.read_text())

    # Deserialize back to ProjectScan
    loaded_scan = ProjectScan.model_validate(cache_json)

    # Verify data matches
    assert loaded_scan.project_root == original_scan.project_root
    assert loaded_scan.project_type == original_scan.project_type
    assert loaded_scan.total_files == original_scan.total_files
    assert loaded_scan.total_functions == original_scan.total_functions
    assert loaded_scan.total_classes == original_scan.total_classes


def test_init_command_end_to_end(tmp_path: Path) -> None:
    """Test init_command creates all expected artifacts."""
    from imp.context.cli import init_command

    # Create a Python project with nested structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("""
def main() -> None:
    print("Hello")
""")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("""
def test_main() -> None:
    assert True
""")

    # Run init_command
    exit_code = init_command(root=tmp_path, format="human")
    assert exit_code == 0

    # Verify all artifacts exist
    assert (tmp_path / ".index.md").exists()
    assert (src_dir / ".index.md").exists()
    assert (tests_dir / ".index.md").exists()
    assert (tmp_path / ".imp" / "scan.json").exists()

    # Verify cache contains expected data
    cache = json.loads((tmp_path / ".imp" / "scan.json").read_text())
    assert cache["total_files"] == 2


def test_index_content_accuracy(tmp_path: Path) -> None:
    """Test that .index.md contains accurate information about code structure."""
    from imp.context.indexer import generate_indexes
    from imp.context.parser import scan_and_parse

    # Create a module with known structure
    (tmp_path / "module.py").write_text("""
\"\"\"A test module.\"\"\"

class Calculator:
    \"\"\"A calculator class.\"\"\"

    def add(self, a: int, b: int) -> int:
        \"\"\"Add two numbers.\"\"\"
        return a + b

    def subtract(self, a: int, b: int) -> int:
        \"\"\"Subtract two numbers.\"\"\"
        return a - b

def standalone_function() -> None:
    \"\"\"A standalone function.\"\"\"
    pass
""")

    # Scan, parse, and generate indexes
    scan_result = scan_and_parse(tmp_path)
    generate_indexes(scan_result, tmp_path)

    # Read the root index
    root_index = (tmp_path / ".index.md").read_text()

    # Should have project structure information
    assert "Project Index" in root_index or "Module" in root_index

    # Read module index (for files in root, it's same as root index conceptually)
    # The actual implementation creates a module index in the directory with the file
    # So look for content that indicates the module was indexed
    assert "1" in root_index  # Should show 1 file or 1 class somewhere


def test_mixed_project_detection(tmp_path: Path) -> None:
    """Test that mixed Python/TypeScript projects are detected correctly."""
    from imp.context.parser import scan_and_parse

    # Create mixed project
    (tmp_path / "app.py").write_text("def main(): pass")
    (tmp_path / "script.ts").write_text("function hello() {}")

    # Scan and parse
    scan_result = scan_and_parse(tmp_path)

    # Should detect as mixed
    assert scan_result.project_type == "mixed"
    assert scan_result.total_files == 2


def test_error_handling_in_pipeline(tmp_path: Path) -> None:
    """Test that pipeline handles parse errors gracefully."""
    from imp.context.parser import scan_and_parse

    # Create a file with syntax error
    (tmp_path / "bad.py").write_text("""
def broken(
    # Missing closing paren and body
""")

    # Should still complete scan (with parse_error set)
    scan_result = scan_and_parse(tmp_path)

    # Should have the file in results
    assert scan_result.total_files == 1

    # Find the module with the bad file
    for dir_mod in scan_result.modules:
        for mod_info in dir_mod.files:
            if "bad.py" in mod_info.file_info.path:
                # Should have parse_error set
                assert mod_info.parse_error is not None
                assert (
                    "SyntaxError" in mod_info.parse_error
                    or "IndentationError" in mod_info.parse_error
                )
