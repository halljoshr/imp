"""Tests for summarizer — AI-powered module summarization."""

from datetime import UTC, datetime

import pytest

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
from imp.types import TokenUsage

# ===== Fixtures =====


def _make_module(
    path: str = "src/",
    files: list[ModuleInfo] | None = None,
    purpose: str | None = None,
) -> DirectoryModule:
    """Helper to build a DirectoryModule for testing."""
    if files is None:
        files = [
            ModuleInfo(
                file_info=FileInfo(
                    path=f"{path}main.py",
                    size_bytes=500,
                    language=Language.PYTHON,
                    line_count=25,
                ),
                functions=[
                    FunctionInfo(
                        name="main",
                        signature="main() -> None",
                        line_number=1,
                        docstring="Entry point.",
                    ),
                ],
                classes=[
                    ClassInfo(
                        name="App",
                        line_number=10,
                        docstring="Main application.",
                        bases=["BaseApp"],
                        methods=[
                            FunctionInfo(
                                name="run",
                                signature="run(self) -> None",
                                line_number=12,
                                is_method=True,
                            ),
                        ],
                    ),
                ],
                imports=[
                    ImportInfo(module="typing", names=["List"], is_from_import=True),
                    ImportInfo(module="imp.types", names=["TokenUsage"], is_from_import=True),
                ],
                module_docstring="Main application module.",
                exports=["App", "main"],
            ),
        ]
    return DirectoryModule(path=path, files=files, purpose=purpose)


def _make_scan(modules: list[DirectoryModule] | None = None) -> ProjectScan:
    """Helper to build a ProjectScan for testing."""
    if modules is None:
        modules = [_make_module()]
    total_files = sum(len(m.files) for m in modules)
    total_functions = sum(len(f.functions) for m in modules for f in m.files)
    total_classes = sum(len(f.classes) for m in modules for f in m.files)
    return ProjectScan(
        project_root="/tmp/project",
        project_type="python",
        modules=modules,
        total_files=total_files,
        total_functions=total_functions,
        total_classes=total_classes,
        scanned_at=datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


async def _mock_invoke(prompt: str) -> tuple[str, TokenUsage]:
    """Mock invoke function that returns a canned summary."""
    return (
        "This module provides core application functionality.",
        TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120),
    )


async def _mock_invoke_with_path(prompt: str) -> tuple[str, TokenUsage]:
    """Mock invoke that includes the module path in its response for tracing."""
    # Extract path from prompt for verification
    if "src/" in prompt:
        return (
            "Source module providing core functionality.",
            TokenUsage(input_tokens=80, output_tokens=15, total_tokens=95),
        )
    return (
        "Generic module.",
        TokenUsage(input_tokens=50, output_tokens=10, total_tokens=60),
    )


# ===== build_prompt Tests =====


def test_build_prompt_includes_module_path() -> None:
    """Test prompt includes the module path."""
    from imp.context.summarizer import build_prompt

    module = _make_module(path="src/auth/")
    prompt = build_prompt(module)
    assert "src/auth/" in prompt


def test_build_prompt_includes_files() -> None:
    """Test prompt includes file names and line counts."""
    from imp.context.summarizer import build_prompt

    module = _make_module()
    prompt = build_prompt(module)
    assert "main.py" in prompt
    assert "25" in prompt  # line count


def test_build_prompt_includes_exports() -> None:
    """Test prompt includes exported names."""
    from imp.context.summarizer import build_prompt

    module = _make_module()
    prompt = build_prompt(module)
    assert "App" in prompt
    assert "main" in prompt


def test_build_prompt_includes_imports() -> None:
    """Test prompt includes import dependencies."""
    from imp.context.summarizer import build_prompt

    module = _make_module()
    prompt = build_prompt(module)
    assert "typing" in prompt or "imp.types" in prompt


def test_build_prompt_includes_plain_imports() -> None:
    """Test prompt includes plain import (not from-import) dependencies."""
    from imp.context.summarizer import build_prompt

    module = DirectoryModule(
        path="lib/",
        files=[
            ModuleInfo(
                file_info=FileInfo(
                    path="lib/util.py",
                    size_bytes=100,
                    language=Language.PYTHON,
                    line_count=5,
                ),
                imports=[
                    ImportInfo(module="os", names=[], is_from_import=False),
                ],
            ),
        ],
    )
    prompt = build_prompt(module)
    assert "import os" in prompt


def test_build_prompt_includes_docstrings() -> None:
    """Test prompt includes module/class/function docstrings."""
    from imp.context.summarizer import build_prompt

    module = _make_module()
    prompt = build_prompt(module)
    assert "Main application module" in prompt or "Entry point" in prompt


def test_build_prompt_includes_classes() -> None:
    """Test prompt includes class info."""
    from imp.context.summarizer import build_prompt

    module = _make_module()
    prompt = build_prompt(module)
    assert "App" in prompt


def test_build_prompt_empty_module() -> None:
    """Test prompt for module with no files."""
    from imp.context.summarizer import build_prompt

    module = DirectoryModule(path="empty/", files=[])
    prompt = build_prompt(module)
    assert "empty/" in prompt


def test_build_prompt_no_docstrings() -> None:
    """Test prompt for module with classes/functions without docstrings."""
    from imp.context.summarizer import build_prompt

    module = DirectoryModule(
        path="nodocs/",
        files=[
            ModuleInfo(
                file_info=FileInfo(
                    path="nodocs/core.py",
                    size_bytes=100,
                    language=Language.PYTHON,
                    line_count=10,
                ),
                functions=[
                    FunctionInfo(
                        name="process",
                        signature="process() -> None",
                        line_number=1,
                        docstring=None,
                    ),
                ],
                classes=[
                    ClassInfo(
                        name="Handler",
                        line_number=5,
                        docstring=None,
                        bases=[],
                    ),
                ],
            ),
        ],
    )
    prompt = build_prompt(module)
    assert "Handler" in prompt
    assert "process" in prompt


def test_build_prompt_minimal_file_no_ast() -> None:
    """Test prompt for module with file but no classes/functions/imports/exports."""
    from imp.context.summarizer import build_prompt

    module = DirectoryModule(
        path="data/",
        files=[
            ModuleInfo(
                file_info=FileInfo(
                    path="data/config.py",
                    size_bytes=50,
                    language=Language.PYTHON,
                    line_count=3,
                ),
            ),
        ],
    )
    prompt = build_prompt(module)
    assert "data/" in prompt
    assert "config.py" in prompt
    # Should NOT have Classes/Functions/Exports/Dependencies sections
    assert "Classes:" not in prompt
    assert "Functions:" not in prompt
    assert "Exports:" not in prompt
    assert "Dependencies:" not in prompt


# ===== summarize_module Tests =====


@pytest.mark.asyncio
async def test_summarize_module_returns_purpose_and_usage() -> None:
    """Test summarize_module returns (purpose, usage) tuple."""
    from imp.context.summarizer import summarize_module

    module = _make_module()
    purpose, usage = await summarize_module(module, _mock_invoke)

    assert isinstance(purpose, str)
    assert len(purpose) > 0
    assert isinstance(usage, TokenUsage)
    assert usage.total_tokens > 0


@pytest.mark.asyncio
async def test_summarize_module_calls_invoke_with_prompt() -> None:
    """Test summarize_module passes built prompt to invoke_fn."""
    from imp.context.summarizer import summarize_module

    received_prompts: list[str] = []

    async def tracking_invoke(prompt: str) -> tuple[str, TokenUsage]:
        received_prompts.append(prompt)
        return "Purpose.", TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)

    module = _make_module(path="src/core/")
    await summarize_module(module, tracking_invoke)

    assert len(received_prompts) == 1
    assert "src/core/" in received_prompts[0]


# ===== summarize_project Tests =====


@pytest.mark.asyncio
async def test_summarize_project_fills_purpose_fields() -> None:
    """Test summarize_project sets purpose on all modules."""
    from imp.context.summarizer import summarize_project

    scan = _make_scan()
    enriched, _summaries, _usage = await summarize_project(scan, _mock_invoke)

    # All modules should have purpose filled
    for module in enriched.modules:
        assert module.purpose is not None
        assert len(module.purpose) > 0


@pytest.mark.asyncio
async def test_summarize_project_returns_summary_entries() -> None:
    """Test summarize_project returns SummaryEntry dict."""
    from imp.context.summarizer import summarize_project
    from imp.context.summary_cache import SummaryEntry

    scan = _make_scan()
    _, summaries, _ = await summarize_project(scan, _mock_invoke)

    assert len(summaries) == 1
    assert "src/" in summaries
    assert isinstance(summaries["src/"], SummaryEntry)


@pytest.mark.asyncio
async def test_summarize_project_aggregates_token_usage() -> None:
    """Test summarize_project sums token usage across all modules."""
    from imp.context.summarizer import summarize_project

    modules = [_make_module(path="src/"), _make_module(path="tests/")]
    scan = _make_scan(modules)
    _, _, usage = await summarize_project(scan, _mock_invoke)

    # Two modules, each with 120 tokens
    assert usage.total_tokens == 240
    assert usage.input_tokens == 200
    assert usage.output_tokens == 40


@pytest.mark.asyncio
async def test_summarize_project_skips_cached_modules() -> None:
    """Test summarize_project skips modules with cached summaries."""
    from imp.context.summarizer import summarize_project
    from imp.context.summary_cache import SummaryEntry

    call_count = 0

    async def counting_invoke(prompt: str) -> tuple[str, TokenUsage]:
        nonlocal call_count
        call_count += 1
        return "New summary.", TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)

    modules = [_make_module(path="src/"), _make_module(path="tests/")]
    scan = _make_scan(modules)

    # Pre-cache src/ summary
    cached = {
        "src/": SummaryEntry(
            purpose="Cached source purpose.",
            summarized_at=datetime.now(UTC),
            model_used="test-model",
        ),
    }
    enriched, _summaries, _usage = await summarize_project(
        scan, counting_invoke, cached_summaries=cached
    )

    # Should only call AI for tests/, not src/
    assert call_count == 1

    # src/ should use cached purpose
    src_module = next(m for m in enriched.modules if m.path == "src/")
    assert src_module.purpose == "Cached source purpose."

    # tests/ should use new AI summary
    tests_module = next(m for m in enriched.modules if m.path == "tests/")
    assert tests_module.purpose == "New summary."


@pytest.mark.asyncio
async def test_summarize_project_preserves_scan_metadata() -> None:
    """Test summarize_project preserves all scan metadata."""
    from imp.context.summarizer import summarize_project

    scan = _make_scan()
    enriched, _, _ = await summarize_project(scan, _mock_invoke)

    assert enriched.project_root == scan.project_root
    assert enriched.project_type == scan.project_type
    assert enriched.total_files == scan.total_files
    assert enriched.total_functions == scan.total_functions
    assert enriched.total_classes == scan.total_classes
    assert enriched.scanned_at == scan.scanned_at


@pytest.mark.asyncio
async def test_summarize_project_no_modules() -> None:
    """Test summarize_project with empty module list."""
    from imp.context.summarizer import summarize_project

    scan = _make_scan(modules=[])
    enriched, summaries, usage = await summarize_project(scan, _mock_invoke)

    assert len(enriched.modules) == 0
    assert len(summaries) == 0
    assert usage.total_tokens == 0


@pytest.mark.asyncio
async def test_summarize_project_with_model_name() -> None:
    """Test summarize_project records model name in SummaryEntry."""
    from imp.context.summarizer import summarize_project

    scan = _make_scan()
    _, summaries, _ = await summarize_project(
        scan, _mock_invoke, model_name="anthropic:claude-haiku-4-5"
    )

    entry = summaries["src/"]
    assert entry.model_used == "anthropic:claude-haiku-4-5"


@pytest.mark.asyncio
async def test_summarize_project_request_count_with_cache() -> None:
    """Test requests count equals AI calls made, not total minus cached."""
    from imp.context.summarizer import summarize_project
    from imp.context.summary_cache import SummaryEntry

    modules = [_make_module(path="src/"), _make_module(path="tests/")]
    scan = _make_scan(modules)

    # Cache one module
    cached = {
        "src/": SummaryEntry(
            purpose="Cached.",
            summarized_at=datetime.now(UTC),
            model_used="test",
        ),
    }
    _, _, usage = await summarize_project(scan, _mock_invoke, cached_summaries=cached)

    # Only tests/ should have been an AI request
    assert usage.requests == 1


@pytest.mark.asyncio
async def test_summarize_project_stale_cache_no_negative_requests() -> None:
    """Test requests count is non-negative even when cache has stale entries."""
    from imp.context.summarizer import summarize_project
    from imp.context.summary_cache import SummaryEntry

    # Only one module exists now
    scan = _make_scan([_make_module(path="src/")])

    # Cache has entries for modules that no longer exist
    cached = {
        "src/": SummaryEntry(
            purpose="Cached.", summarized_at=datetime.now(UTC), model_used="test"
        ),
        "old_module/": SummaryEntry(
            purpose="Stale.", summarized_at=datetime.now(UTC), model_used="test"
        ),
        "deleted/": SummaryEntry(
            purpose="Gone.", summarized_at=datetime.now(UTC), model_used="test"
        ),
    }
    _, _, usage = await summarize_project(scan, _mock_invoke, cached_summaries=cached)

    # src/ was cached, no AI calls made — requests must be 0, not -2
    assert usage.requests == 0
