"""CLI commands for context/indexing."""

import json
from pathlib import Path

from rich import print as rprint

from imp.context.indexer import generate_indexes, save_cache
from imp.context.parser import scan_and_parse


def init_command(root: Path, format: str = "human") -> int:
    """Initialize project indexes.

    Performs L1+L2 scan, generates .index.md files, and saves cache to .imp/.

    Args:
        root: Project root directory
        format: Output format (human, json, jsonl)

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

    try:
        # 2. Scan + parse (L1+L2)
        scan_result = scan_and_parse(root)

        # 3. Generate .index.md files
        index_files = generate_indexes(scan_result, root)

        # 4. Save cache to .imp/
        cache_file = save_cache(scan_result, root)

        # 5. Output summary in requested format
        if format == "json":
            output = {
                "project_root": str(root),
                "project_type": scan_result.project_type,
                "total_files": scan_result.total_files,
                "total_functions": scan_result.total_functions,
                "total_classes": scan_result.total_classes,
                "index_files": [str(p) for p in index_files],
                "cache_file": str(cache_file),
            }
            print(json.dumps(output, indent=2))

        elif format == "jsonl":
            # Output one line per index file created
            for index_path in index_files:
                print(json.dumps({"type": "index_file", "path": str(index_path)}))
            # Output cache file
            print(json.dumps({"type": "cache_file", "path": str(cache_file)}))
            # Output summary
            print(
                json.dumps(
                    {
                        "type": "summary",
                        "project_type": scan_result.project_type,
                        "total_files": scan_result.total_files,
                        "total_functions": scan_result.total_functions,
                        "total_classes": scan_result.total_classes,
                    }
                )
            )

        else:  # human
            rprint(f"\n[green]✓[/green] Initialized project indexes at [cyan]{root}[/cyan]\n")
            rprint(f"Project type: [bold]{scan_result.project_type}[/bold]")
            rprint(
                f"Scanned: {scan_result.total_files} files, "
                f"{scan_result.total_functions} functions, "
                f"{scan_result.total_classes} classes"
            )
            rprint(f"\nGenerated {len(index_files)} .index.md files")
            rprint(f"Cache saved to [dim]{cache_file}[/dim]\n")

        return 0

    except Exception as e:
        if format == "human":
            rprint(f"[red]Error:[/red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1
