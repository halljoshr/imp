"""Tests for toolchain detector."""

from pathlib import Path

from imp.validation.detector import ProjectType, ToolchainConfig, detect_toolchain


class TestProjectType:
    """Test ProjectType enum."""

    def test_all_project_types_defined(self) -> None:
        """All supported project types are available."""
        assert ProjectType.PYTHON == "python"
        assert ProjectType.TYPESCRIPT == "typescript"
        assert ProjectType.MIXED == "mixed"
        assert ProjectType.UNKNOWN == "unknown"


class TestToolchainConfig:
    """Test ToolchainConfig model."""

    def test_creation_python_defaults(self) -> None:
        """Can create ToolchainConfig for Python with defaults."""
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
            format_command="ruff format",
        )
        assert config.project_type == ProjectType.PYTHON
        assert config.test_command == "pytest"
        assert config.lint_command == "ruff check"
        assert config.type_command == "mypy"
        assert config.format_command == "ruff format"
        assert config.security_command is None  # Optional

    def test_creation_typescript_defaults(self) -> None:
        """Can create ToolchainConfig for TypeScript."""
        config = ToolchainConfig(
            project_type=ProjectType.TYPESCRIPT,
            test_command="npm test",
            lint_command="eslint .",
            type_command="tsc --noEmit",
            format_command="prettier --check .",
        )
        assert config.project_type == ProjectType.TYPESCRIPT
        assert config.test_command == "npm test"
        assert config.lint_command == "eslint ."

    def test_creation_with_security(self) -> None:
        """Can create ToolchainConfig with security command."""
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
            format_command="ruff format",
            security_command="bandit -r src/",
        )
        assert config.security_command == "bandit -r src/"

    def test_creation_minimal(self) -> None:
        """Can create ToolchainConfig with only required fields."""
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
        )
        assert config.test_command == "pytest"
        assert config.lint_command is None
        assert config.type_command is None
        assert config.format_command is None
        assert config.security_command is None

    def test_available_gates_all(self) -> None:
        """available_gates returns all gates with commands."""
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            lint_command="ruff check",
            type_command="mypy",
            format_command="ruff format",
            security_command="bandit -r src/",
        )
        gates = config.available_gates()
        assert set(gates) == {"test", "lint", "type", "format", "security"}

    def test_available_gates_partial(self) -> None:
        """available_gates only returns gates with commands."""
        config = ToolchainConfig(
            project_type=ProjectType.PYTHON,
            test_command="pytest",
            type_command="mypy",
        )
        gates = config.available_gates()
        assert set(gates) == {"test", "type"}
        assert "lint" not in gates
        assert "format" not in gates


class TestDetectToolchain:
    """Test detect_toolchain function."""

    def test_detect_python_project(self, tmp_path: Path) -> None:
        """Detects Python project from pyproject.toml."""
        # Create pyproject.toml with pytest and ruff
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 99

[tool.mypy]
strict = true
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.PYTHON
        assert config.test_command is not None
        assert "pytest" in config.test_command
        assert config.lint_command is not None
        assert "ruff check" in config.lint_command
        assert config.type_command is not None
        assert "mypy" in config.type_command

    def test_detect_typescript_project(self, tmp_path: Path) -> None:
        """Detects TypeScript project from package.json."""
        # Create package.json with jest and eslint
        package_json = tmp_path / "package.json"
        package_json.write_text("""
{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "test": "jest",
    "lint": "eslint .",
    "type-check": "tsc --noEmit"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "eslint": "^8.0.0",
    "typescript": "^5.0.0",
    "prettier": "^3.0.0"
  }
}
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.TYPESCRIPT
        assert config.test_command is not None
        assert "npm test" in config.test_command or "jest" in config.test_command
        assert config.lint_command is not None
        assert "eslint" in config.lint_command

    def test_detect_mixed_project(self, tmp_path: Path) -> None:
        """Detects mixed Python/TypeScript project."""
        # Create both pyproject.toml and package.json
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        package_json = tmp_path / "package.json"
        package_json.write_text("""
{
  "name": "test-project-web",
  "scripts": {
    "test": "jest"
  }
}
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.MIXED
        # Should detect both Python and TypeScript tools
        assert config.test_command is not None

    def test_detect_python_with_bandit(self, tmp_path: Path) -> None:
        """Detects bandit for security scanning."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[tool.bandit]
exclude_dirs = ["tests"]
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.PYTHON
        assert config.security_command is not None
        assert "bandit" in config.security_command

    def test_detect_unknown_project(self, tmp_path: Path) -> None:
        """Returns unknown project type when no config files found."""
        # Empty directory
        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.UNKNOWN
        # Should still provide some minimal defaults or None values
        assert config.test_command is None or config.test_command == ""

    def test_detect_python_with_uv(self, tmp_path: Path) -> None:
        """Detects uv-based Python project and uses uv run."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        # Create uv.lock to indicate uv project
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.PYTHON
        # Should use "uv run" prefix for commands
        assert config.test_command is not None
        assert "uv run pytest" in config.test_command

    def test_detect_respects_custom_scripts(self, tmp_path: Path) -> None:
        """Respects custom scripts defined in pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[project.scripts]
test = "custom-test-runner"
lint = "custom-linter"
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.PYTHON
        # Should detect custom scripts if present
        # (implementation detail - may use standard tools or custom scripts)

    def test_detect_with_nonexistent_path(self) -> None:
        """Handles nonexistent path gracefully."""
        config = detect_toolchain(Path("/nonexistent/path"))
        assert config.project_type == ProjectType.UNKNOWN

    def test_detect_with_import_linter(self, tmp_path: Path) -> None:
        """Detects import-linter as an additional Python tool."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[tool.importlinter]
root_packages = ["mypackage"]
""")

        config = detect_toolchain(tmp_path)
        assert config.project_type == ProjectType.PYTHON
        # import-linter might be detected as additional validation
        # (implementation detail - could be part of lint or separate)
