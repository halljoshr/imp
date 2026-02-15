"""CLI commands for context/indexing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from rich import print as rprint

from imp.context.indexer import generate_indexes, save_cache
from imp.context.parser import scan_and_parse
from imp.context.staleness import detect_stale_modules, load_previous_scan
from imp.context.summarizer import summarize_project
from imp.context.summary_cache import load_summaries, save_summaries

if TYPE_CHECKING:
    from imp.context.summarizer import InvokeFn


def init_command(
    root: Path,
    format: str = "human",
    summarize: bool = False,
    model: str | None = None,
    invoke_fn: InvokeFn | None = None,
) -> int:
    """Initialize project indexes.

    Performs L1+L2 scan, generates .index.md files, and saves cache to .imp/.
    Optionally runs L3 AI summarization with --summarize.

    Args:
        root: Project root directory
        format: Output format (human, json, jsonl)
        summarize: Whether to run AI summarization (L3)
        model: AI model name for summarization
        invoke_fn: Async callable for AI invocation (DI)

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    # 1. Validate root exists
    if not root.exists():
        if format == "human":
            rprint(f"[red]Error:[/red] Project root does not exist: {root}")
        else:
            print(json.dumps({"error": f"Project root does not exist: {root}"}))
        return 1

    # 2. Validate summarize requirements
    if summarize and invoke_fn is None:
        if format == "human":
            rprint(
                "[red]Error:[/red] --summarize requires an AI provider. "
                "Pass --model to configure one."
            )
        else:
            print(
                json.dumps(
                    {
                        "error": "--summarize requires an AI provider. "
                        "Pass --model to configure one."
                    }
                )
            )
        return 1

    try:
        # 3. Scan + parse (L1+L2)
        scan_result = scan_and_parse(root)

        # 4. Optionally run L3 summarization
        summarized_count = 0
        summary_tokens = 0
        if summarize and invoke_fn is not None:
            # Load cached summaries
            cached = load_summaries(root)

            # Invalidate stale summaries — re-summarize modules whose files changed
            previous = load_previous_scan(root)
            if previous is not None:
                stale = detect_stale_modules(scan_result, previous)
                for s in stale:
                    cached.pop(s.module_path, None)

            # Run summarization
            scan_result, summaries, usage = asyncio.run(
                summarize_project(
                    scan_result,
                    invoke_fn,
                    cached_summaries=cached,
                    model_name=model or "unknown",
                )
            )
            summarized_count = len(summaries)
            summary_tokens = usage.total_tokens

            # Save summaries cache
            save_summaries(summaries, root)

        # 5. Generate .index.md files
        index_files = generate_indexes(scan_result, root)

        # 6. Save cache to .imp/
        cache_file = save_cache(scan_result, root)

        # 7. Output summary in requested format
        if format == "json":
            output: dict[str, object] = {
                "project_root": str(root),
                "project_type": scan_result.project_type,
                "total_files": scan_result.total_files,
                "total_functions": scan_result.total_functions,
                "total_classes": scan_result.total_classes,
                "index_files": [str(p) for p in index_files],
                "cache_file": str(cache_file),
            }
            if summarize:
                output["summarized_modules"] = summarized_count
                output["summary_tokens"] = summary_tokens
            print(json.dumps(output, indent=2))

        elif format == "jsonl":
            # Output one line per index file created
            for index_path in index_files:
                print(json.dumps({"type": "index_file", "path": str(index_path)}))
            # Output cache file
            print(json.dumps({"type": "cache_file", "path": str(cache_file)}))
            # Output summary
            summary_data: dict[str, object] = {
                "type": "summary",
                "project_type": scan_result.project_type,
                "total_files": scan_result.total_files,
                "total_functions": scan_result.total_functions,
                "total_classes": scan_result.total_classes,
            }
            if summarize:
                summary_data["summarized_modules"] = summarized_count
                summary_data["summary_tokens"] = summary_tokens
            print(json.dumps(summary_data))

        else:  # human
            rprint(f"\n[green]✓[/green] Initialized project indexes at [cyan]{root}[/cyan]\n")
            rprint(f"Project type: [bold]{scan_result.project_type}[/bold]")
            rprint(
                f"Scanned: {scan_result.total_files} files, "
                f"{scan_result.total_functions} functions, "
                f"{scan_result.total_classes} classes"
            )
            if summarize:
                rprint(f"Summarized: {summarized_count} modules ({summary_tokens:,} tokens)")
            rprint(f"\nGenerated {len(index_files)} .index.md files")
            rprint(f"Cache saved to [dim]{cache_file}[/dim]\n")

        return 0

    except Exception as e:
        if format == "human":
            rprint(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1
