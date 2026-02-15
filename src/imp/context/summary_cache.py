"""Summary cache — persist AI-generated module summaries.

Stores SummaryEntry objects keyed by module path in .imp/summaries.json.
Survives re-runs so AI summaries don't need to be regenerated every time.
"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SummaryEntry(BaseModel):
    """Cached AI summary for a module."""

    purpose: str
    summarized_at: datetime
    model_used: str

    model_config = ConfigDict(frozen=True)


def save_summaries(summaries: dict[str, SummaryEntry], project_root: Path) -> Path:
    """Save summaries to .imp/summaries.json.

    Creates .imp directory if it doesn't exist.

    Args:
        summaries: Module path -> SummaryEntry mapping
        project_root: Root directory of the project

    Returns:
        Path to the written summaries.json file
    """
    imp_dir = project_root / ".imp"
    imp_dir.mkdir(exist_ok=True)

    summaries_path = imp_dir / "summaries.json"
    data = {key: entry.model_dump(mode="json") for key, entry in summaries.items()}
    summaries_path.write_text(json.dumps(data, indent=2))

    return summaries_path


def load_summaries(project_root: Path) -> dict[str, SummaryEntry]:
    """Load summaries from .imp/summaries.json.

    Returns empty dict if file doesn't exist, is corrupt, or has invalid structure.

    Args:
        project_root: Root directory of the project

    Returns:
        Module path -> SummaryEntry mapping
    """
    summaries_path = project_root / ".imp" / "summaries.json"
    if not summaries_path.exists():
        return {}

    try:
        data = json.loads(summaries_path.read_text())
        return {key: SummaryEntry.model_validate(value) for key, value in data.items()}
    except (json.JSONDecodeError, Exception):
        return {}
