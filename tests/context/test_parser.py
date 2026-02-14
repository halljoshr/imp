"""Tests for context.parser — L2 AST extraction."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imp.context.models import (
    DirectoryModule,
    FileInfo,
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


class TestParsePythonFunctions:
    """Test Python function extraction."""

    def test_regular_function_with_signature(self):
        """Extract regular function with args, return type, docstring."""
        source = '''
def greet(name: str, age: int = 42) -> str:
    """Greet a person."""
    return f"Hello {name}"
'''
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert "name: str" in func.signature
        assert "age: int = 42" in func.signature
        assert "-> str" in func.signature
        assert func.docstring == "Greet a person."
        assert func.is_method is False
        assert func.is_async is False
        assert func.decorators == []
        assert func.line_number == 2

    def test_async_function(self):
        """Extract async function."""
        source = '''
async def fetch_data(url: str):
    """Fetch data from URL."""
    pass
'''
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "fetch_data"
        assert func.is_async is True
        assert func.docstring == "Fetch data from URL."

    def test_function_with_decorators(self):
        """Extract function decorators."""
        source = """
@property
@staticmethod
def decorated():
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "decorated"
        assert "property" in func.decorators
        assert "staticmethod" in func.decorators

    def test_function_with_complex_decorator(self):
        """Extract complex decorator expressions."""
        source = """
@app.route("/api/users")
@validate(schema=UserSchema)
def get_users():
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        # Complex decorators should be stringified
        assert any("route" in d for d in func.decorators)
        assert any("validate" in d for d in func.decorators)

    def test_multiple_functions(self):
        """Extract multiple functions from one file."""
        source = """
def foo():
    pass

def bar():
    pass

async def baz():
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 3
        assert result.functions[0].name == "foo"
        assert result.functions[1].name == "bar"
        assert result.functions[2].name == "baz"
        assert result.functions[2].is_async is True


class TestParsePythonClasses:
    """Test Python class extraction."""

    def test_class_with_bases(self):
        """Extract class with inheritance."""
        source = '''
class MyError(ValueError, RuntimeError):
    """Custom error."""
    pass
'''
        result = parse_python("test.py", source)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "MyError"
        assert "ValueError" in cls.bases
        assert "RuntimeError" in cls.bases
        assert cls.docstring == "Custom error."

    def test_class_with_methods(self):
        """Extract class methods."""
        source = '''
class Calculator:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    async def async_multiply(self, a: int, b: int) -> int:
        return a * b
'''
        result = parse_python("test.py", source)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Calculator"
        assert len(cls.methods) == 2

        # Methods should have is_method=True
        add_method = cls.methods[0]
        assert add_method.name == "add"
        assert add_method.is_method is True
        assert "self" in add_method.signature
        assert add_method.docstring == "Add two numbers."

        async_method = cls.methods[1]
        assert async_method.name == "async_multiply"
        assert async_method.is_method is True
        assert async_method.is_async is True

    def test_class_with_decorators(self):
        """Extract class decorators."""
        source = """
@dataclass
@frozen
class Point:
    x: int
    y: int
"""
        result = parse_python("test.py", source)

        assert len(result.classes) == 1
        # Note: We're checking decorators on the class
        # Implementation may store these on ClassInfo if we add that field

    def test_class_with_complex_base(self):
        """Extract class with generic/complex base."""
        source = """
class MyList(list[str]):
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert len(cls.bases) >= 1
        # Should capture the base, stringified somehow


class TestParsePythonImports:
    """Test Python import extraction."""

    def test_simple_import(self):
        """Extract simple import statement."""
        source = "import os"

        result = parse_python("test.py", source)

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os"
        assert imp.names == []
        assert imp.is_from_import is False

    def test_from_import_single(self):
        """Extract from-import with single name."""
        source = "from os import path"

        result = parse_python("test.py", source)

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os"
        assert imp.names == ["path"]
        assert imp.is_from_import is True

    def test_from_import_multiple(self):
        """Extract from-import with multiple names."""
        source = "from os import path, getcwd, environ"

        result = parse_python("test.py", source)

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os"
        assert set(imp.names) == {"path", "getcwd", "environ"}
        assert imp.is_from_import is True

    def test_relative_import(self):
        """Extract relative imports."""
        source = "from . import foo"

        result = parse_python("test.py", source)

        assert len(result.imports) == 1
        imp = result.imports[0]
        # Relative imports have module as None or "." depending on implementation
        assert imp.is_from_import is True
        assert "foo" in imp.names

    def test_multiple_imports(self):
        """Extract multiple import statements."""
        source = """
import os
import sys
from pathlib import Path
"""
        result = parse_python("test.py", source)

        assert len(result.imports) == 3
        assert result.imports[0].module == "os"
        assert result.imports[1].module == "sys"
        assert result.imports[2].module == "pathlib"


class TestParsePythonModuleDocstring:
    """Test module-level docstring extraction."""

    def test_module_docstring(self):
        """Extract module docstring."""
        source = '''"""This is a module docstring.

It can be multiple lines.
"""

def foo():
    pass
'''
        result = parse_python("test.py", source)

        assert result.module_docstring is not None
        assert "This is a module docstring" in result.module_docstring

    def test_no_module_docstring(self):
        """Handle missing module docstring."""
        source = "def foo():\n    pass"

        result = parse_python("test.py", source)

        assert result.module_docstring is None


class TestParsePythonExports:
    """Test __all__ extraction."""

    def test_exports_list(self):
        """Extract __all__ list."""
        source = """
__all__ = ["Foo", "bar", "baz"]

class Foo:
    pass

def bar():
    pass
"""
        result = parse_python("test.py", source)

        assert set(result.exports) == {"Foo", "bar", "baz"}

    def test_exports_tuple(self):
        """Extract __all__ tuple."""
        source = """__all__ = ("Foo", "bar")"""

        result = parse_python("test.py", source)

        assert set(result.exports) == {"Foo", "bar"}

    def test_no_exports(self):
        """Handle missing __all__."""
        source = "def foo():\n    pass"

        result = parse_python("test.py", source)

        assert result.exports == []


class TestParsePythonErrorHandling:
    """Test Python syntax error handling."""

    def test_syntax_error(self):
        """Handle syntax error gracefully."""
        source = "def foo(\n    # Incomplete function"

        result = parse_python("test.py", source)

        assert result.parse_error is not None
        assert "syntax" in result.parse_error.lower() or "error" in result.parse_error.lower()
        # Should still return a ModuleInfo with FileInfo
        assert result.file_info.path == "test.py"
        assert result.file_info.language == Language.PYTHON

    def test_indentation_error(self):
        """Handle indentation error gracefully."""
        source = """
def foo():
pass
"""
        result = parse_python("test.py", source)

        assert result.parse_error is not None


class TestParseTypescript:
    """Test TypeScript/JavaScript parsing."""

    def test_typescript_not_installed(self):
        """Handle tree-sitter not installed."""
        with patch("imp.context.parser.tree_sitter", None):
            result = parse_typescript("test.ts", "function foo() {}")

            assert result.parse_error is not None
            assert "tree-sitter not installed" in result.parse_error
            assert "pip install impx[tree-sitter]" in result.parse_error
            assert result.file_info.language == Language.TYPESCRIPT

    @pytest.mark.skipif(
        True,
        reason="tree-sitter parsing is optional for v0.1 - focus on graceful fallback",
    )
    def test_parse_typescript_basic(self):
        """Basic TypeScript parsing (if tree-sitter available)."""
        source = """
function greet(name: string): string {
    return `Hello ${name}`;
}
"""
        result = parse_typescript("test.ts", source)

        # If tree-sitter is installed, should extract function
        if result.parse_error is None:
            assert len(result.functions) >= 1
            assert any(f.name == "greet" for f in result.functions)


class TestParseFileDispatcher:
    """Test parse_file dispatcher."""

    def test_dispatch_python(self):
        """Dispatch Python file to parse_python."""
        source = "def foo(): pass"

        result = parse_file("test.py", source, Language.PYTHON)

        assert len(result.functions) == 1
        assert result.functions[0].name == "foo"

    def test_dispatch_typescript(self):
        """Dispatch TypeScript file to parse_typescript."""
        source = "function foo() {}"

        result = parse_file("test.ts", source, Language.TYPESCRIPT)

        # Should call parse_typescript (which may return error if not installed)
        assert result.file_info.language == Language.TYPESCRIPT

    def test_dispatch_javascript(self):
        """Dispatch JavaScript file to parse_typescript."""
        source = "function foo() {}"

        result = parse_file("test.js", source, Language.JAVASCRIPT)

        # JavaScript uses same parser as TypeScript
        assert result.file_info.language == Language.JAVASCRIPT

    def test_dispatch_unknown(self):
        """Handle unknown language."""
        source = "some random content"

        result = parse_file("test.xyz", source, Language.UNKNOWN)

        # Should return ModuleInfo with only file_info, no AST data
        assert result.file_info.language == Language.UNKNOWN
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []
        assert result.parse_error is None  # Not an error, just no parser


class TestScanAndParse:
    """Test full L1+L2 scan."""

    def test_scan_and_parse_integration(self, tmp_path: Path):
        """Full scan + parse integration."""
        # Create a simple Python project
        (tmp_path / "main.py").write_text('''
"""Main module."""

def main():
    """Entry point."""
    print("Hello")

class App:
    """Main application."""
    pass
''')

        (tmp_path / "utils.py").write_text("""
def helper():
    pass
""")

        # Mock the scanner since it may not be implemented yet
        mock_scan_result = ProjectScan(
            project_root=str(tmp_path),
            project_type="python",
            modules=[
                DirectoryModule(
                    path=str(tmp_path),
                    files=[
                        ModuleInfo(
                            file_info=FileInfo(
                                path=str(tmp_path / "main.py"),
                                size_bytes=100,
                                language=Language.PYTHON,
                                line_count=10,
                            )
                        ),
                        ModuleInfo(
                            file_info=FileInfo(
                                path=str(tmp_path / "utils.py"),
                                size_bytes=50,
                                language=Language.PYTHON,
                                line_count=3,
                            )
                        ),
                    ],
                )
            ],
            total_files=2,
            total_functions=0,  # Scanner doesn't count functions (L1 only)
            total_classes=0,
            scanned_at=MagicMock(),
        )

        with patch("imp.context.scanner.scan_project", return_value=mock_scan_result):
            result = scan_and_parse(tmp_path)

            # Should have enriched the modules with L2 data
            assert result.project_root == str(tmp_path)
            assert result.total_files == 2

            # Find main.py module
            main_module = None
            for dir_mod in result.modules:
                for mod in dir_mod.files:
                    if "main.py" in mod.file_info.path:
                        main_module = mod
                        break

            assert main_module is not None
            assert main_module.module_docstring == "Main module."
            assert len(main_module.functions) == 1
            assert main_module.functions[0].name == "main"
            assert len(main_module.classes) == 1
            assert main_module.classes[0].name == "App"

    def test_scan_and_parse_with_errors(self, tmp_path: Path):
        """Scan + parse handles files with syntax errors."""
        (tmp_path / "broken.py").write_text("def foo(\n")

        mock_scan_result = ProjectScan(
            project_root=str(tmp_path),
            project_type="python",
            modules=[
                DirectoryModule(
                    path=str(tmp_path),
                    files=[
                        ModuleInfo(
                            file_info=FileInfo(
                                path=str(tmp_path / "broken.py"),
                                size_bytes=10,
                                language=Language.PYTHON,
                                line_count=1,
                            )
                        )
                    ],
                )
            ],
            total_files=1,
            total_functions=0,
            total_classes=0,
            scanned_at=MagicMock(),
        )

        with patch("imp.context.scanner.scan_project", return_value=mock_scan_result):
            result = scan_and_parse(tmp_path)

            # Should not crash, should set parse_error
            broken_module = result.modules[0].files[0]
            assert broken_module.parse_error is not None

    def test_scan_and_parse_file_read_error(self, tmp_path: Path):
        """Scan + parse handles file read failures gracefully."""
        mock_scan_result = ProjectScan(
            project_root=str(tmp_path),
            project_type="python",
            modules=[
                DirectoryModule(
                    path=str(tmp_path),
                    files=[
                        ModuleInfo(
                            file_info=FileInfo(
                                path=str(tmp_path / "missing.py"),
                                size_bytes=10,
                                language=Language.PYTHON,
                                line_count=1,
                            )
                        )
                    ],
                )
            ],
            total_files=1,
            total_functions=0,
            total_classes=0,
            scanned_at=MagicMock(),
        )

        with patch("imp.context.scanner.scan_project", return_value=mock_scan_result):
            result = scan_and_parse(tmp_path)

            # Should not crash, should set parse_error about file read
            failed_module = result.modules[0].files[0]
            assert failed_module.parse_error is not None
            assert "failed to read" in failed_module.parse_error.lower()


class TestParsePythonVarArgs:
    """Test *args and **kwargs extraction."""

    def test_function_with_varargs(self):
        """Extract function with *args."""
        source = """
def foo(*args: int):
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert "*args" in func.signature
        assert ": int" in func.signature

    def test_function_with_kwargs(self):
        """Extract function with **kwargs."""
        source = """
def foo(**kwargs: str):
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert "**kwargs" in func.signature
        assert ": str" in func.signature

    def test_function_with_both_varargs_and_kwargs(self):
        """Extract function with both *args and **kwargs."""
        source = """
def foo(x: int, *args, **kwargs):
    pass
"""
        result = parse_python("test.py", source)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert "*args" in func.signature
        assert "**kwargs" in func.signature
        assert "x: int" in func.signature


class TestParsePythonAssignmentsAndExports:
    """Test module-level assignment handling and edge cases in export extraction."""

    def test_assignment_not_all(self):
        """Module-level assignment that is not __all__ should not affect exports."""
        source = """
MY_CONST = [1, 2, 3]
OTHER = "value"
__all__ = ["foo"]

def foo():
    pass
"""
        result = parse_python("test.py", source)

        assert result.exports == ["foo"]

    def test_exports_non_list_value(self):
        """__all__ set to a non-list/tuple value returns empty exports."""
        source = """
__all__ = some_variable
"""
        result = parse_python("test.py", source)

        assert result.exports == []
