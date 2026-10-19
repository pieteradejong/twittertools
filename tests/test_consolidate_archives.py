"""Tests for scripts/consolidate_archives.py — dedup of archives/ into one tree.

All tests run on small synthetic exports in tmp_path. The near-duplicate video
tests generate a tiny MP4 with ffmpeg and are skipped where it isn't installed.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import consolidate_archives as ca  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def manifest(gen):
    return "window.__THAR_CONFIG = " + json.dumps(
        {"archiveInfo": {"generationDate": gen, "isPartialArchive": False}, "dataTypes": {}}
    )


def make_export(root: Path, name: str, gen: str, files: dict) -> Path:
    base = root / name
    for rel, data in {"data/manifest.js": manifest(gen), **files}.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return base


def zip_folder(folder: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(folder).as_posix())
    return zip_path


@pytest.fixture
def archives(tmp_path, monkeypatch):
    d = tmp_path / "archives"
    d.mkdir()
    monkeypatch.setattr(ca, "TRASH", tmp_path / "Trash")
    return d


def inode(p: Path):
    st = p.stat()
    return st.st_dev, st.st_ino


def snapshot(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_ino)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #
def test_plan_names_folders_by_generation_date(archives):
    make_export(archives, "twitter-2025-02-24-abc", "2025-02-24T10:00:00Z", {"data/a.js": "a"})
    old = make_export(archives, "tmp-old", "2024-01-01T00:00:00Z", {"data/a.js": "a"})
    zip_folder(old, archives / "twitter-2024-01-01.zip")
    shutil.rmtree(old)  # only the zip remains for 2024
    plan = ca.make_plan(archives)
    assert [(a.name, b.name) for a, b in plan.rename] == [
        ("twitter-2025-02-24-abc", "twitter-archive-2025-02-24")
    ]
    assert [(z.name, d.name) for z, d in plan.unzip] == [
        ("twitter-2024-01-01.zip", "twitter-archive-2024-01-01")
    ]
    assert not plan.problems


def test_plan_changes_nothing(archives, capsys):
    f = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z", {"data/a.js": "x"})
    make_export(archives, "twitter-archive-2025-02-01", "2025-02-01T00:00:00Z", {"data/a.js": "x"})
    zip_folder(f, archives / "twitter-2025-01-01.zip")
    before = snapshot(archives)
    assert ca.cmd_plan(archives) == 0
    assert snapshot(archives) == before
    assert "exact duplicates" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Apply: exact duplicates, zips
# --------------------------------------------------------------------------- #
def test_apply_hardlinks_identical_files_and_trashes_zips(archives, tmp_path):
    a = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z",
                    {"data/same.js": "same", "data/only-a.js": "a", "data/changed.js": "v1"})
    b = make_export(archives, "twitter-archive-2025-02-01", "2025-02-01T00:00:00Z",
                    {"data/same.js": "same", "data/changed.js": "v2"})
    zip_folder(a, archives / "twitter-2025-01-01.zip")

    assert ca.cmd_apply(archives) == 0

    assert inode(a / "data/same.js") == inode(b / "data/same.js")
    assert inode(a / "data/changed.js") != inode(b / "data/changed.js")
    assert (a / "data/changed.js").read_text() == "v1"
    assert not os.access(b / "data/same.js", os.W_OK)  # read-only, so no silent edits
    assert not (archives / "twitter-2025-01-01.zip").exists()
    assert list((tmp_path / "Trash").glob("twitter-2025-01-01.zip-*"))
    assert ca.verify(archives) == []


def test_apply_unzips_an_export_that_has_no_folder(archives):
    src = make_export(archives, "tmp", "2024-05-05T00:00:00Z", {"data/x.js": "x"})
    zip_folder(src, archives / "twitter-2024-05-05.zip")
    shutil.rmtree(src)
    assert ca.cmd_apply(archives) == 0
    assert (archives / "twitter-archive-2024-05-05" / "data" / "x.js").read_text() == "x"


def test_zip_folder_mismatch_aborts_before_anything_is_deleted(archives):
    a = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z", {"data/a.js": "a"})
    z = zip_folder(a, archives / "twitter-2025-01-01.zip")
    (a / "data" / "a.js").write_text("tampered")
    with pytest.raises(ca.ConsolidationError, match="differs"):
        ca.cmd_apply(archives)
    assert z.exists()
    assert not (archives / "checksums").exists()


def test_unsafe_zip_path_is_refused(archives):
    z = archives / "twitter-2024-01-01.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("data/manifest.js", manifest("2024-01-01T00:00:00Z"))
        zf.writestr("../escape.txt", "x")
    with pytest.raises(ca.ConsolidationError, match="unsafe path"):
        ca.cmd_apply(archives)
    assert not (archives.parent / "escape.txt").exists()


def test_apply_is_idempotent(archives):
    make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z", {"data/s.js": "s"})
    make_export(archives, "twitter-archive-2025-02-01", "2025-02-01T00:00:00Z", {"data/s.js": "s"})
    assert ca.cmd_apply(archives) == 0
    before = snapshot(archives)
    assert ca.cmd_apply(archives) == 0
    assert snapshot(archives) == before


# --------------------------------------------------------------------------- #
# Verify
# --------------------------------------------------------------------------- #
def test_verify_catches_tampered_missing_and_extra_files(archives):
    a = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z",
                    {"data/a.js": "a", "data/b.js": "b"})
    ca.cmd_apply(archives)
    p = a / "data" / "a.js"
    p.chmod(0o600)
    p.write_text("tampered")
    (a / "data" / "b.js").unlink()
    (a / "data" / "new.js").write_text("n")
    failures = "\n".join(ca.verify(archives))
    assert "a.js: content does not match" in failures
    assert "b.js: missing" in failures
    assert "new.js: not in checksums" in failures


def test_verify_ignores_finder_junk(archives):
    a = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z", {"data/a.js": "a"})
    ca.cmd_apply(archives)
    (a / ".DS_Store").write_bytes(b"\0")
    assert ca.verify(archives) == []


# --------------------------------------------------------------------------- #
# Near-duplicate videos
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def mp4(tmp_path_factory) -> bytes:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("v") / "v.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=5:duration=1",
         "-c:v", "mpeg4", "-movflags", "+faststart", str(out)],
        check=True,
    )
    return out.read_bytes()


def with_new_creation_time(data: bytes, seconds: int) -> bytes:
    """Rewrite mvhd's creation time: the kind of edit X makes between exports."""
    i = data.index(b"mvhd")
    buf = bytearray(data)
    buf[i + 8 : i + 12] = struct.pack(">I", seconds)  # after version+flags
    return bytes(buf)


def corrupt_mdat(data: bytes) -> bytes:
    i = data.index(b"mdat") + 64
    buf = bytearray(data)
    buf[i] ^= 0xFF
    return bytes(buf)


@needs_ffmpeg
def test_metadata_only_video_is_merged_and_rebuildable(archives, mp4):
    rel = "data/tweets_media/1-x.mp4"
    old_bytes = with_new_creation_time(mp4, 1_000_000)
    old = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z", {rel: old_bytes})
    new = make_export(archives, "twitter-archive-2025-02-01", "2025-02-01T00:00:00Z", {rel: mp4})

    assert ca.cmd_apply(archives) == 0

    assert inode(old / rel) == inode(new / rel)
    patches = ca.load_patches(archives)
    rec = patches[f"twitter-archive-2025-01-01/{rel}"]
    rebuilt = ca.apply_patch((old / rel).read_bytes(), rec["runs"])
    assert rebuilt == old_bytes  # the original survives as a patch
    assert ca.verify(archives) == []


@needs_ffmpeg
def test_video_differing_outside_the_header_is_kept(archives, mp4):
    rel = "data/tweets_media/1-x.mp4"
    old = make_export(archives, "twitter-archive-2025-01-01", "2025-01-01T00:00:00Z",
                      {rel: corrupt_mdat(mp4)})
    new = make_export(archives, "twitter-archive-2025-02-01", "2025-02-01T00:00:00Z", {rel: mp4})

    assert ca.cmd_apply(archives) == 0

    assert inode(old / rel) != inode(new / rel)
    assert ca.load_patches(archives) == {}
    assert (old / rel).read_bytes() == corrupt_mdat(mp4)


def test_diff_runs_groups_contiguous_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"0123456789")
    b.write_bytes(b"0xx34567y9")
    assert ca.diff_runs(a, b, 10) == [(1, b"12"), (8, b"8")]
    assert ca.diff_runs(a, b, 2) is None  # 3 bytes differ, over the limit
