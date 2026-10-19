"""Locate the newest X archive export under archives/.

Exports live in archives/twitter-archive-YYYY-MM-DD/ (see
scripts/consolidate_archives.py). The ISO date in the name sorts
chronologically, so the last folder is the newest export.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_NAME = re.compile(r"twitter-archive-\d{4}-\d{2}-\d{2}")


def latest_archive(repo_root: Path = REPO_ROOT) -> Path:
    """The newest archives/twitter-archive-YYYY-MM-DD folder; raises if none exist."""
    archives = repo_root / "archives"
    exports = sorted(
        p for p in archives.glob("twitter-archive-*")
        if p.is_dir() and EXPORT_NAME.fullmatch(p.name)
    )
    if not exports:
        raise FileNotFoundError(f"no twitter-archive-YYYY-MM-DD folder under {archives}")
    return exports[-1]
