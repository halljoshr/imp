"""Summarizer — AI-powered module summarization (L3).

Uses dependency injection to avoid importing imp.providers.
Pass an InvokeFn callable that wraps the AI provider.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from imp.context.models import DirectoryModule, ProjectScan
from imp.context.summary_cache import SummaryEntry
from imp.types import TokenUsage

# DI type — caller provides an async function: prompt -> (purpose, usage)
InvokeFn = Callable[[str], Awaitable[tuple[str, TokenUsage]]]


def build_prompt(module: DirectoryModule) -> str:
    """Build summarization prompt from L1+L2 data.

    Includes module path, file list with line counts, exports, imports,
    and docstrings to give the AI maximum context for summarization.

    Args:
        module: Directory module with L1+L2 data

    Returns:
        Prompt string for AI summarization
    """
    lines = [
        f"Summarize what the module at path `{module.path}` does in business terms.",
        "Write 2-3 sentences describing its purpose and responsibilities.",
        "",
        f"Module path: {module.path}",
    ]

    if not module.files:
        lines.append("(No source files)")
        return "\n".join(lines)

    # Files with line counts
    lines.append("")
    lines.append("Files:")
    for f in module.files:
        lines.append(f"- {f.file_info.path} ({f.file_info.line_count} lines)")
        if f.module_docstring:
            lines.append(f"  Docstring: {f.module_docstring}")

    # Exports
    all_exports = [name for f in module.files for name in f.exports]
    if all_exports:
        lines.append("")
        lines.append(f"Exports: {', '.join(all_exports)}")

    # Classes
    all_classes = [c for f in module.files for c in f.classes]
    if all_classes:
        lines.append("")
        lines.append("Classes:")
        for cls in all_classes:
            bases = f" (extends {', '.join(cls.bases)})" if cls.bases else ""
            lines.append(f"- {cls.name}{bases}")
            if cls.docstring:
                lines.append(f"  {cls.docstring}")

    # Functions
    all_functions = [fn for f in module.files for fn in f.functions if not fn.is_method]
    if all_functions:
        lines.append("")
        lines.append("Functions:")
        for fn in all_functions:
            lines.append(f"- {fn.signature}")
            if fn.docstring:
                lines.append(f"  {fn.docstring}")

    # Imports
    all_imports = [imp for f in module.files for imp in f.imports]
    if all_imports:
        lines.append("")
        lines.append("Dependencies:")
        for imp in all_imports:
            if imp.names:
                lines.append(f"- from {imp.module} import {', '.join(imp.names)}")
            else:
                lines.append(f"- import {imp.module}")

    return "\n".join(lines)


async def summarize_module(
    module: DirectoryModule,
    invoke_fn: InvokeFn,
) -> tuple[str, TokenUsage]:
    """Summarize a single module using AI.

    Args:
        module: Directory module to summarize
        invoke_fn: Async function that calls the AI provider

    Returns:
        Tuple of (purpose_string, token_usage)
    """
    prompt = build_prompt(module)
    return await invoke_fn(prompt)


async def summarize_project(
    scan: ProjectScan,
    invoke_fn: InvokeFn,
    cached_summaries: dict[str, SummaryEntry] | None = None,
    model_name: str = "unknown",
) -> tuple[ProjectScan, dict[str, SummaryEntry], TokenUsage]:
    """Summarize all modules, skipping cached ones.

    Args:
        scan: Project scan with L1+L2 data
        invoke_fn: Async function that calls the AI provider
        cached_summaries: Previously cached summaries to skip
        model_name: Model name to record in SummaryEntry

    Returns:
        Tuple of (enriched_scan, summaries_dict, total_usage)
    """
    if cached_summaries is None:
        cached_summaries = {}

    total_input = 0
    total_output = 0
    total_tokens = 0
    total_requests = 0
    summaries: dict[str, SummaryEntry] = {}
    enriched_modules: list[DirectoryModule] = []

    for module in scan.modules:
        # Check cache
        if module.path in cached_summaries:
            entry = cached_summaries[module.path]
            enriched_modules.append(module.model_copy(update={"purpose": entry.purpose}))
            summaries[module.path] = entry
            continue

        # Call AI
        purpose, usage = await summarize_module(module, invoke_fn)
        total_input += usage.input_tokens
        total_output += usage.output_tokens
        total_tokens += usage.total_tokens
        total_requests += 1

        enriched_modules.append(module.model_copy(update={"purpose": purpose}))
        summaries[module.path] = SummaryEntry(
            purpose=purpose,
            summarized_at=datetime.now(UTC),
            model_used=model_name,
        )

    enriched_scan = scan.model_copy(update={"modules": enriched_modules})
    total_usage = TokenUsage(
        input_tokens=total_input,
        output_tokens=total_output,
        total_tokens=total_tokens,
        requests=total_requests,
    )

    return enriched_scan, summaries, total_usage
