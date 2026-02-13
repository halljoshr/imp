"""Interview skill utilities.

This module provides helpers for accessing portable interview skills and domain libraries.
"""

from pathlib import Path

__all__ = [
    "get_default_skill_path",
    "get_domain_library_path",
    "list_available_domains",
]


def get_default_skill_path() -> Path:
    """Return the path to the default interview skill.

    Returns:
        Path to the default SKILL.md file

    Example:
        >>> skill_path = get_default_skill_path()
        >>> with open(skill_path) as f:
        ...     skill_content = f.read()
    """
    return Path(__file__).parent / "default" / "SKILL.md"


def get_domain_library_path(domain: str) -> Path:
    """Return the path to a domain library file.

    Args:
        domain: Domain name (e.g., 'software-requirements')

    Returns:
        Path to the domain library markdown file

    Raises:
        FileNotFoundError: If the domain library doesn't exist

    Example:
        >>> library_path = get_domain_library_path("software-requirements")
        >>> with open(library_path) as f:
        ...     library_content = f.read()
    """
    path = Path(__file__).parent / "default" / "domains" / f"{domain}.md"
    if not path.exists():
        available = ", ".join(list_available_domains())
        msg = f"Domain library '{domain}' not found. Available: {available}"
        raise FileNotFoundError(msg)
    return path


def list_available_domains() -> list[str]:
    """List all available domain libraries.

    Returns:
        List of domain names (without .md extension)

    Example:
        >>> domains = list_available_domains()
        >>> print(domains)
        ['software-requirements']
    """
    domains_dir = Path(__file__).parent / "default" / "domains"
    if not domains_dir.exists():
        return []

    return [p.stem for p in domains_dir.glob("*.md") if p.is_file() and p.stem != "README"]
