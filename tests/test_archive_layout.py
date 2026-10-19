"""Guards for the on-disk archive layout.

The X archive exports live under `archives/` (gitignored). Scripts reach
into that tree through `archive_paths.latest_archive()` or a glob, and the
failure mode is silent: a glob that matches nothing loads zero rows and
exits 0. These tests turn that into a red test.

They are skipped when no archive is present (fresh clone / CI), so they never
block someone who has not downloaded an export.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = REPO_ROOT / "archives"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import archive_paths  # noqa: E402

has_archives = pytest.mark.skipif(
    not ARCHIVES.is_dir(), reason="no local archives/ tree (fresh clone)"
)


@has_archives
def test_latest_archive_has_data():
    """The export the scripts resolve to must hold a tweets.js."""
    assert (archive_paths.latest_archive() / "data" / "tweets.js").is_file()


def test_latest_archive_picks_newest(tmp_path):
    for name in ("twitter-archive-2024-01-01", "twitter-archive-2025-06-01",
                 "twitter-archive-2025-02-01", "twitter-2099-01-01.zip"):
        (tmp_path / "archives" / name).mkdir(parents=True)
    assert archive_paths.latest_archive(tmp_path).name == "twitter-archive-2025-06-01"


def test_latest_archive_raises_when_empty(tmp_path):
    (tmp_path / "archives").mkdir()
    with pytest.raises(FileNotFoundError):
        archive_paths.latest_archive(tmp_path)


@has_archives
def test_like_glob_finds_archives():
    """enrich_likes.load_archives() globs for like.js — it must not come back empty.

    Regression: the glob was `twitter-*/data/like*.js`, anchored at the repo
    root. Moving the exports into `archives/` made it match nothing, and
    `--load-archives` then reported success having loaded zero likes.
    """
    import enrich_likes as el  # noqa: PLC0415

    files = el.find_like_files(REPO_ROOT)
    assert files, "no like.js found under archives/ — archive discovery is broken"


@has_archives
def test_one_folder_per_export_with_checksums():
    """After consolidation (scripts/consolidate_archives.py): no zips or
    hash-named folders remain, and every export has its checksum file."""
    leftovers = [p.name for p in ARCHIVES.iterdir() if p.name.startswith("twitter-")
                 and not re.fullmatch(r"twitter-archive-\d{4}-\d{2}-\d{2}", p.name)]
    assert not leftovers, f"unconsolidated exports: {leftovers}"
    for folder in ARCHIVES.glob("twitter-archive-*"):
        assert (ARCHIVES / "checksums" / f"{folder.name}.sha256").is_file(), folder.name


@pytest.mark.parametrize(
    "script", ["scripts/load_local_data.py", "scripts/import_relationships.py"]
)
def test_scripts_do_not_hardcode_an_export(script):
    """Scripts resolve the export at run time; a dated literal goes stale
    (and once loaded zero rows silently when the exports moved)."""
    text = (REPO_ROOT / script).read_text()
    assert not re.search(r"twitter-archive-\d", text), f"{script} hard-codes an export"
    assert "latest_archive" in text


@has_archives
def test_archives_are_gitignored():
    """archives/ holds DMs, IP audit logs and a phone number. This repo is public."""
    import subprocess  # noqa: PLC0415

    r = subprocess.run(
        ["git", "check-ignore", "-q", "archives"], cwd=REPO_ROOT, check=False
    )
    assert r.returncode == 0, "archives/ is NOT gitignored — do not commit"
