"""Tests for context models.

Following three-tier TDD: write all tests BEFORE implementation.
Target: 100% branch coverage.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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


class TestLanguage:
    """Test Language enum."""

    def test_all_languages_defined(self) -> None:
        """All language types are available."""
        assert Language.PYTHON == "python"
        assert Language.TYPESCRIPT == "typescript"
        assert Language.JAVASCRIPT == "javascript"
        assert Language.UNKNOWN == "unknown"

    def test_languages_are_strings(self) -> None:
        """Language values are strings for JSON serialization."""
        for language in Language:
            assert isinstance(language.value, str)


class TestFileInfo:
    """Test FileInfo model."""

    def test_creation_with_all_fields(self) -> None:
        """Can create FileInfo with all required fields."""
        file_info = FileInfo(
            path="src/auth/session.py",
            size_bytes=4096,
            language=Language.PYTHON,
            line_count=150,
        )
        assert file_info.path == "src/auth/session.py"
        assert file_info.size_bytes == 4096
        assert file_info.language == Language.PYTHON
        assert file_info.line_count == 150

    def test_immutability(self) -> None:
        """FileInfo is frozen."""
        file_info = FileInfo(
            path="test.py",
            size_bytes=100,
            language=Language.PYTHON,
            line_count=10,
        )
        with pytest.raises(ValidationError):
            file_info.path = "changed.py"  # type: ignore[misc]

    def test_json_serialization(self) -> None:
        """FileInfo can be serialized to JSON."""
        file_info = FileInfo(
            path="test.ts",
            size_bytes=2048,
            language=Language.TYPESCRIPT,
            line_count=75,
        )
        data = file_info.model_dump()
        assert data["path"] == "test.ts"
        assert data["size_bytes"] == 2048
        assert data["language"] == "typescript"
        assert data["line_count"] == 75

    def test_required_fields(self) -> None:
        """All fields are required."""
        with pytest.raises(ValidationError):
            FileInfo(  # type: ignore[call-arg]
                path="test.py",
                size_bytes=100,
                # missing language
                line_count=10,
            )


class TestFunctionInfo:
    """Test FunctionInfo model."""

    def test_creation_minimal_function(self) -> None:
        """Can create function with only required fields."""
        func = FunctionInfo(
            name="calculate_total",
            signature="calculate_total(items: list[Item]) -> float",
            line_number=42,
        )
        assert func.name == "calculate_total"
        assert func.signature == "calculate_total(items: list[Item]) -> float"
        assert func.line_number == 42
        assert func.docstring is None
        assert func.is_method is False
        assert func.is_async is False
        assert func.decorators == []

    def test_creation_method_with_docstring(self) -> None:
        """Can create method with docstring."""
        func = FunctionInfo(
            name="process_payment",
            signature="process_payment(self, amount: Decimal) -> PaymentResult",
            line_number=89,
            docstring="Process a payment transaction.\n\nArgs:\n    amount: Payment amount",
            is_method=True,
        )
        assert func.is_method is True
        assert func.docstring is not None
        assert "Process a payment transaction" in func.docstring

    def test_creation_async_function(self) -> None:
        """Can create async function."""
        func = FunctionInfo(
            name="fetch_user",
            signature="async def fetch_user(user_id: int) -> User",
            line_number=120,
            is_async=True,
        )
        assert func.is_async is True

    def test_creation_with_decorators(self) -> None:
        """Can create function with decorators."""
        func = FunctionInfo(
            name="cached_query",
            signature="cached_query(key: str) -> dict",
            line_number=55,
            decorators=["@cache", "@retry(max_attempts=3)"],
        )
        assert len(func.decorators) == 2
        assert "@cache" in func.decorators

    def test_immutability(self) -> None:
        """FunctionInfo is frozen."""
        func = FunctionInfo(name="test", signature="test() -> None", line_number=1)
        with pytest.raises(ValidationError):
            func.is_async = True  # type: ignore[misc]

    def test_json_serialization(self) -> None:
        """FunctionInfo can be serialized to JSON."""
        func = FunctionInfo(
            name="helper",
            signature="helper(x: int) -> int",
            line_number=10,
            is_method=False,
            is_async=True,
            decorators=["@staticmethod"],
        )
        data = func.model_dump()
        assert data["name"] == "helper"
        assert data["line_number"] == 10
        assert data["is_async"] is True
        assert len(data["decorators"]) == 1


class TestClassInfo:
    """Test ClassInfo model."""

    def test_creation_minimal_class(self) -> None:
        """Can create class with only required fields."""
        cls = ClassInfo(
            name="User",
            line_number=25,
        )
        assert cls.name == "User"
        assert cls.line_number == 25
        assert cls.docstring is None
        assert cls.bases == []
        assert cls.methods == []

    def test_creation_with_docstring(self) -> None:
        """Can create class with docstring."""
        cls = ClassInfo(
            name="PaymentProcessor",
            line_number=100,
            docstring="Handles payment processing and validation.",
        )
        assert cls.docstring == "Handles payment processing and validation."

    def test_creation_with_base_classes(self) -> None:
        """Can create class with base classes."""
        cls = ClassInfo(
            name="AdminUser",
            line_number=50,
            bases=["User", "PermissionMixin"],
        )
        assert len(cls.bases) == 2
        assert "User" in cls.bases
        assert "PermissionMixin" in cls.bases

    def test_creation_with_methods(self) -> None:
        """Can create class with methods."""
        method1 = FunctionInfo(
            name="__init__",
            signature="__init__(self, name: str)",
            line_number=51,
            is_method=True,
        )
        method2 = FunctionInfo(
            name="save",
            signature="save(self) -> None",
            line_number=55,
            is_method=True,
        )
        cls = ClassInfo(
            name="Model",
            line_number=50,
            methods=[method1, method2],
        )
        assert len(cls.methods) == 2
        assert cls.methods[0].name == "__init__"
        assert cls.methods[1].name == "save"

    def test_immutability(self) -> None:
        """ClassInfo is frozen."""
        cls = ClassInfo(name="Test", line_number=1)
        with pytest.raises(ValidationError):
            cls.name = "Changed"  # type: ignore[misc]

    def test_json_serialization_with_nested_methods(self) -> None:
        """ClassInfo can be serialized to JSON with nested methods."""
        method = FunctionInfo(
            name="method",
            signature="method(self) -> None",
            line_number=11,
            is_method=True,
        )
        cls = ClassInfo(
            name="TestClass",
            line_number=10,
            bases=["BaseClass"],
            methods=[method],
        )
        data = cls.model_dump()
        assert data["name"] == "TestClass"
        assert len(data["bases"]) == 1
        assert len(data["methods"]) == 1
        assert data["methods"][0]["name"] == "method"


class TestImportInfo:
    """Test ImportInfo model."""

    def test_creation_simple_import(self) -> None:
        """Can create simple import statement."""
        imp = ImportInfo(
            module="os",
        )
        assert imp.module == "os"
        assert imp.names == []
        assert imp.is_from_import is False

    def test_creation_from_import(self) -> None:
        """Can create from-import statement."""
        imp = ImportInfo(
            module="datetime",
            names=["datetime", "timezone"],
            is_from_import=True,
        )
        assert imp.module == "datetime"
        assert len(imp.names) == 2
        assert "datetime" in imp.names
        assert "timezone" in imp.names
        assert imp.is_from_import is True

    def test_creation_import_with_names(self) -> None:
        """Can create import with specific names."""
        imp = ImportInfo(
            module="typing",
            names=["List", "Dict", "Optional"],
            is_from_import=True,
        )
        assert len(imp.names) == 3
        assert "Optional" in imp.names

    def test_immutability(self) -> None:
        """ImportInfo is frozen."""
        imp = ImportInfo(module="sys")
        with pytest.raises(ValidationError):
            imp.module = "os"  # type: ignore[misc]

    def test_json_serialization(self) -> None:
        """ImportInfo can be serialized to JSON."""
        imp = ImportInfo(
            module="pathlib",
            names=["Path"],
            is_from_import=True,
        )
        data = imp.model_dump()
        assert data["module"] == "pathlib"
        assert data["names"] == ["Path"]
        assert data["is_from_import"] is True


class TestModuleInfo:
    """Test ModuleInfo model."""

    def test_creation_minimal_module(self) -> None:
        """Can create module with only FileInfo."""
        file_info = FileInfo(
            path="src/utils.py",
            size_bytes=500,
            language=Language.PYTHON,
            line_count=20,
        )
        module = ModuleInfo(file_info=file_info)
        assert module.file_info == file_info
        assert module.functions == []
        assert module.classes == []
        assert module.imports == []
        assert module.module_docstring is None
        assert module.exports == []
        assert module.parse_error is None

    def test_creation_with_module_docstring(self) -> None:
        """Can create module with docstring."""
        file_info = FileInfo(
            path="src/auth.py",
            size_bytes=1000,
            language=Language.PYTHON,
            line_count=50,
        )
        module = ModuleInfo(
            file_info=file_info,
            module_docstring="Authentication and authorization utilities.",
        )
        assert module.module_docstring == "Authentication and authorization utilities."

    def test_creation_with_functions(self) -> None:
        """Can create module with functions."""
        file_info = FileInfo(
            path="src/helpers.py",
            size_bytes=800,
            language=Language.PYTHON,
            line_count=40,
        )
        func1 = FunctionInfo(name="helper1", signature="helper1() -> None", line_number=5)
        func2 = FunctionInfo(name="helper2", signature="helper2() -> str", line_number=10)
        module = ModuleInfo(
            file_info=file_info,
            functions=[func1, func2],
        )
        assert len(module.functions) == 2
        assert module.functions[0].name == "helper1"

    def test_creation_with_classes(self) -> None:
        """Can create module with classes."""
        file_info = FileInfo(
            path="src/models.py",
            size_bytes=2000,
            language=Language.PYTHON,
            line_count=100,
        )
        cls1 = ClassInfo(name="User", line_number=10)
        cls2 = ClassInfo(name="Admin", line_number=50)
        module = ModuleInfo(
            file_info=file_info,
            classes=[cls1, cls2],
        )
        assert len(module.classes) == 2
        assert module.classes[1].name == "Admin"

    def test_creation_with_imports(self) -> None:
        """Can create module with imports."""
        file_info = FileInfo(
            path="src/main.py",
            size_bytes=1500,
            language=Language.PYTHON,
            line_count=60,
        )
        imp1 = ImportInfo(module="os")
        imp2 = ImportInfo(module="typing", names=["List"], is_from_import=True)
        module = ModuleInfo(
            file_info=file_info,
            imports=[imp1, imp2],
        )
        assert len(module.imports) == 2
        assert module.imports[0].module == "os"

    def test_creation_with_exports(self) -> None:
        """Can create module with exports."""
        file_info = FileInfo(
            path="src/api.py",
            size_bytes=1200,
            language=Language.PYTHON,
            line_count=50,
        )
        module = ModuleInfo(
            file_info=file_info,
            exports=["create_app", "run_server", "APIClient"],
        )
        assert len(module.exports) == 3
        assert "create_app" in module.exports

    def test_creation_with_parse_error(self) -> None:
        """Can create module with parse error."""
        file_info = FileInfo(
            path="src/broken.py",
            size_bytes=300,
            language=Language.PYTHON,
            line_count=15,
        )
        module = ModuleInfo(
            file_info=file_info,
            parse_error="SyntaxError: invalid syntax at line 12",
        )
        assert module.parse_error is not None
        assert "SyntaxError" in module.parse_error

    def test_creation_complete_module(self) -> None:
        """Can create module with all fields populated."""
        file_info = FileInfo(
            path="src/complete.py",
            size_bytes=5000,
            language=Language.PYTHON,
            line_count=200,
        )
        func = FunctionInfo(name="func", signature="func() -> None", line_number=10)
        cls = ClassInfo(name="Class", line_number=20)
        imp = ImportInfo(module="sys")
        module = ModuleInfo(
            file_info=file_info,
            functions=[func],
            classes=[cls],
            imports=[imp],
            module_docstring="Complete module.",
            exports=["func", "Class"],
        )
        assert len(module.functions) == 1
        assert len(module.classes) == 1
        assert len(module.imports) == 1
        assert module.module_docstring is not None
        assert len(module.exports) == 2

    def test_immutability(self) -> None:
        """ModuleInfo is frozen."""
        file_info = FileInfo(
            path="test.py",
            size_bytes=100,
            language=Language.PYTHON,
            line_count=5,
        )
        module = ModuleInfo(file_info=file_info)
        with pytest.raises(ValidationError):
            module.module_docstring = "Changed"  # type: ignore[misc]

    def test_json_serialization_nested_models(self) -> None:
        """ModuleInfo can be serialized to JSON with nested models."""
        file_info = FileInfo(
            path="test.py",
            size_bytes=100,
            language=Language.PYTHON,
            line_count=5,
        )
        func = FunctionInfo(name="f", signature="f() -> None", line_number=1)
        cls = ClassInfo(name="C", line_number=5)
        imp = ImportInfo(module="os")
        module = ModuleInfo(
            file_info=file_info,
            functions=[func],
            classes=[cls],
            imports=[imp],
            exports=["f"],
        )
        data = module.model_dump()
        assert data["file_info"]["path"] == "test.py"
        assert len(data["functions"]) == 1
        assert len(data["classes"]) == 1
        assert len(data["imports"]) == 1
        assert len(data["exports"]) == 1


class TestDirectoryModule:
    """Test DirectoryModule model."""

    def test_creation_minimal_directory(self) -> None:
        """Can create directory with path and empty files."""
        directory = DirectoryModule(
            path="src/auth",
            files=[],
        )
        assert directory.path == "src/auth"
        assert directory.files == []
        assert directory.purpose is None

    def test_creation_with_files(self) -> None:
        """Can create directory with files."""
        file_info1 = FileInfo(
            path="src/auth/session.py",
            size_bytes=500,
            language=Language.PYTHON,
            line_count=25,
        )
        module1 = ModuleInfo(file_info=file_info1)
        file_info2 = FileInfo(
            path="src/auth/user.py",
            size_bytes=600,
            language=Language.PYTHON,
            line_count=30,
        )
        module2 = ModuleInfo(file_info=file_info2)
        directory = DirectoryModule(
            path="src/auth",
            files=[module1, module2],
        )
        assert len(directory.files) == 2
        assert directory.files[0].file_info.path == "src/auth/session.py"

    def test_creation_with_purpose(self) -> None:
        """Can create directory with purpose description."""
        file_info = FileInfo(
            path="src/utils/helpers.py",
            size_bytes=300,
            language=Language.PYTHON,
            line_count=15,
        )
        module = ModuleInfo(file_info=file_info)
        directory = DirectoryModule(
            path="src/utils",
            files=[module],
            purpose="Utility functions and helpers for common operations.",
        )
        assert directory.purpose is not None
        assert "Utility functions" in directory.purpose

    def test_immutability(self) -> None:
        """DirectoryModule is frozen."""
        directory = DirectoryModule(path="src/test", files=[])
        with pytest.raises(ValidationError):
            directory.path = "src/changed"  # type: ignore[misc]

    def test_json_serialization(self) -> None:
        """DirectoryModule can be serialized to JSON."""
        file_info = FileInfo(
            path="src/test.py",
            size_bytes=100,
            language=Language.PYTHON,
            line_count=5,
        )
        module = ModuleInfo(file_info=file_info)
        directory = DirectoryModule(
            path="src",
            files=[module],
            purpose="Source code",
        )
        data = directory.model_dump()
        assert data["path"] == "src"
        assert len(data["files"]) == 1
        assert data["purpose"] == "Source code"


class TestProjectScan:
    """Test ProjectScan model."""

    def test_creation_minimal_scan(self) -> None:
        """Can create scan with minimal required fields."""
        scan = ProjectScan(
            project_root="/Users/josh/project",
            project_type="python",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=datetime(2026, 2, 14, 10, 30, 0, tzinfo=UTC),
        )
        assert scan.project_root == "/Users/josh/project"
        assert scan.project_type == "python"
        assert scan.modules == []
        assert scan.total_files == 0
        assert scan.total_functions == 0
        assert scan.total_classes == 0

    def test_creation_with_modules(self) -> None:
        """Can create scan with modules."""
        file_info = FileInfo(
            path="src/main.py",
            size_bytes=1000,
            language=Language.PYTHON,
            line_count=50,
        )
        func = FunctionInfo(name="main", signature="main() -> None", line_number=10)
        cls = ClassInfo(name="App", line_number=20)
        module = ModuleInfo(
            file_info=file_info,
            functions=[func],
            classes=[cls],
        )
        directory = DirectoryModule(path="src", files=[module])
        scan = ProjectScan(
            project_root="/Users/josh/myproject",
            project_type="python",
            modules=[directory],
            total_files=1,
            total_functions=1,
            total_classes=1,
            scanned_at=datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC),
        )
        assert len(scan.modules) == 1
        assert scan.modules[0].path == "src"
        assert scan.total_files == 1
        assert scan.total_functions == 1
        assert scan.total_classes == 1

    def test_project_type_values(self) -> None:
        """Can create scan with different project types."""
        timestamp = datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)
        scan_python = ProjectScan(
            project_root="/project",
            project_type="python",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=timestamp,
        )
        assert scan_python.project_type == "python"

        scan_ts = ProjectScan(
            project_root="/project",
            project_type="typescript",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=timestamp,
        )
        assert scan_ts.project_type == "typescript"

        scan_mixed = ProjectScan(
            project_root="/project",
            project_type="mixed",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=timestamp,
        )
        assert scan_mixed.project_type == "mixed"

        scan_unknown = ProjectScan(
            project_root="/project",
            project_type="unknown",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=timestamp,
        )
        assert scan_unknown.project_type == "unknown"

    def test_immutability(self) -> None:
        """ProjectScan is frozen."""
        scan = ProjectScan(
            project_root="/test",
            project_type="python",
            modules=[],
            total_files=0,
            total_functions=0,
            total_classes=0,
            scanned_at=datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC),
        )
        with pytest.raises(ValidationError):
            scan.project_type = "typescript"  # type: ignore[misc]

    def test_json_serialization_complete(self) -> None:
        """ProjectScan can be serialized to JSON with complete nested structure."""
        file_info = FileInfo(
            path="src/test.py",
            size_bytes=500,
            language=Language.PYTHON,
            line_count=25,
        )
        func = FunctionInfo(name="test_func", signature="test_func() -> None", line_number=5)
        module = ModuleInfo(file_info=file_info, functions=[func])
        directory = DirectoryModule(path="src", files=[module], purpose="Source code")
        scan = ProjectScan(
            project_root="/project",
            project_type="python",
            modules=[directory],
            total_files=1,
            total_functions=1,
            total_classes=0,
            scanned_at=datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC),
        )
        data = scan.model_dump()
        assert data["project_root"] == "/project"
        assert data["project_type"] == "python"
        assert len(data["modules"]) == 1
        assert data["modules"][0]["path"] == "src"
        assert len(data["modules"][0]["files"]) == 1
        assert data["total_files"] == 1
        assert data["total_functions"] == 1
        assert data["total_classes"] == 0
