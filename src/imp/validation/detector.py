"""Toolchain detection for projects."""

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


class ProjectType(StrEnum):
    """Supported project types."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ToolchainConfig(BaseModel):
    """Configuration for project validation toolchain.

    Defines which tools are available and how to run them.
    """

    project_type: ProjectType
    test_command: str | None = None
    lint_command: str | None = None
    type_command: str | None = None
    format_command: str | None = None
    security_command: str | None = None

    def available_gates(self) -> list[str]:
        """Get list of available gate types based on configured commands."""
        gates = []
        if self.test_command:
            gates.append("test")
        if self.lint_command:
            gates.append("lint")
        if self.type_command:
            gates.append("type")
        if self.format_command:
            gates.append("format")
        if self.security_command:
            gates.append("security")
        return gates


def detect_toolchain(project_root: Path) -> ToolchainConfig:
    """Auto-detect project toolchain from config files.

    Args:
        project_root: Root directory of the project

    Returns:
        ToolchainConfig with detected commands
    """
    if not project_root.exists():
        return ToolchainConfig(project_type=ProjectType.UNKNOWN)

    pyproject_path = project_root / "pyproject.toml"
    package_json_path = project_root / "package.json"
    uv_lock_path = project_root / "uv.lock"

    has_python = pyproject_path.exists()
    has_typescript = package_json_path.exists()
    has_uv = uv_lock_path.exists()

    # Determine project type
    if has_python and has_typescript:
        project_type = ProjectType.MIXED
    elif has_python:
        project_type = ProjectType.PYTHON
    elif has_typescript:
        project_type = ProjectType.TYPESCRIPT
    else:
        return ToolchainConfig(project_type=ProjectType.UNKNOWN)

    # Build command prefix for Python (uv run if uv project)
    python_prefix = "uv run " if has_uv else ""

    # Detect Python tools
    test_cmd = None
    lint_cmd = None
    type_cmd = None
    format_cmd = None
    security_cmd = None

    if has_python:
        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)

            # Test: pytest if configured
            if "tool" in pyproject and "pytest" in pyproject["tool"]:
                test_cmd = f"{python_prefix}pytest"

            # Lint: ruff if configured
            if "tool" in pyproject and "ruff" in pyproject["tool"]:
                lint_cmd = f"{python_prefix}ruff check"
                format_cmd = f"{python_prefix}ruff format"

            # Type: mypy if configured
            if "tool" in pyproject and "mypy" in pyproject["tool"]:
                type_cmd = f"{python_prefix}mypy src/"

            # Security: bandit if configured
            if "tool" in pyproject and "bandit" in pyproject["tool"]:
                security_cmd = f"{python_prefix}bandit -r src/"

        except Exception:
            # Malformed TOML or other error - return partial detection
            pass

    # Detect TypeScript tools
    if has_typescript:
        try:
            with open(package_json_path) as f:
                package_json = json.load(f)

            scripts = package_json.get("scripts", {})
            dev_deps = package_json.get("devDependencies", {})

            # Test: jest/vitest via npm test
            if "test" in scripts:
                if not test_cmd:  # Don't override Python test command in mixed projects
                    test_cmd = "npm test"
                elif project_type == ProjectType.MIXED:
                    # In mixed projects, keep Python test command
                    pass

            # Lint: eslint if in devDependencies
            if "eslint" in dev_deps and not lint_cmd:
                # Prefer direct eslint command for better clarity
                lint_cmd = "eslint ."

            # Type: tsc if typescript is present
            if "typescript" in dev_deps:
                if "type-check" in scripts:
                    if not type_cmd:
                        type_cmd = "npm run type-check"
                else:
                    if not type_cmd:
                        type_cmd = "tsc --noEmit"

            # Format: prettier if in devDependencies
            if "prettier" in dev_deps and not format_cmd:
                format_cmd = "prettier --check ."

        except Exception:
            # Malformed JSON or other error - return partial detection
            pass

    return ToolchainConfig(
        project_type=project_type,
        test_command=test_cmd,
        lint_command=lint_cmd,
        type_command=type_cmd,
        format_command=format_cmd,
        security_command=security_cmd,
    )
