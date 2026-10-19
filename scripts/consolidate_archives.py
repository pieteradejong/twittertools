#!/usr/bin/env python3
"""
Consolidate the X archive exports in `archives/` into one deduplicated tree.

End state: one unpacked folder per export, named `twitter-archive-YYYY-MM-DD`
after its manifest's generationDate. Files that are byte-identical across
exports (same SHA-256) are hardlinked to a single inode and made read-only.
Nothing is lost:

  - `archives/checksums/<export>.sha256` records the SHA-256 of every original
    file, taken *before* any deduplication.
  - Near-duplicate videos (same name and size, a handful of bytes different,
    all inside the MP4 `moov` header, identical ffmpeg stream hashes) are
    replaced by the newest copy. The original bytes at each differing offset
    are kept in `archives/checksums/media-patches.json`, so every original
    file can be rebuilt exactly. `verify` does that for every file.
  - A zip is moved to the Trash only after its folder matches every entry by
    CRC-32 and size, and only after `verify` passes.

Usage:
    python scripts/consolidate_archives.py plan     # what would happen; changes nothing
    python scripts/consolidate_archives.py apply    # do it (stops at the first failed check)
    python scripts/consolidate_archives.py verify   # every file matches its original SHA-256

Background and decisions: kept in the local, untracked project notes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import zipfile
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from src.archive_db import ARCHIVES_DIR, ArchiveSource, discover_sources  # noqa: E402

TRASH = Path.home() / ".Trash"
IGNORED_NAMES = {".DS_Store"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4a", ".m4v"}
MAX_PATCH_BYTES = 64  # more differing bytes than this is not "metadata only"


class ConsolidationError(Exception):
    """A check failed; nothing past that point was done."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def crc32_file(path: Path) -> int:
    c = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            c = zlib.crc32(block, c)
    return c & 0xFFFFFFFF


def export_files(folder: Path) -> Dict[str, Path]:
    """Relative path -> file, for every regular file in an export (Finder junk excluded)."""
    return {
        p.relative_to(folder).as_posix(): p
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.is_symlink() and p.name not in IGNORED_NAMES
    }


def canonical_name(src: ArchiveSource) -> str:
    return "twitter-archive-" + src.manifest()["archiveInfo"]["generationDate"][:10]


def generation_date(src: ArchiveSource) -> str:
    return src.manifest()["archiveInfo"]["generationDate"]


def mp4_box_range(path: Path, box: bytes = b"moov") -> Optional[Tuple[int, int]]:
    """(start, end) byte range of a top-level MP4 box, or None."""
    size_total = path.stat().st_size
    with open(path, "rb") as f:
        pos = 0
        while pos + 8 <= size_total:
            f.seek(pos)
            header = f.read(16)
            size = int.from_bytes(header[:4], "big")
            kind = header[4:8]
            if size == 1:
                size = int.from_bytes(header[8:16], "big")
            elif size == 0:
                size = size_total - pos
            if size < 8:
                return None
            if kind == box:
                return pos, pos + size
            pos += size
    return None


def diff_runs(a: Path, b: Path, limit: int) -> Optional[List[Tuple[int, bytes]]]:
    """Runs of bytes where a differs from b, as (offset, a's bytes).
    None if the files differ in size or in more than `limit` bytes."""
    if a.stat().st_size != b.stat().st_size:
        return None
    runs: List[Tuple[int, bytearray]] = []
    count = 0
    offset = 0
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ba, bb = fa.read(1 << 20), fb.read(1 << 20)
            if not ba:
                break
            if ba != bb:
                for i, (x, y) in enumerate(zip(ba, bb)):
                    if x != y:
                        count += 1
                        if count > limit:
                            return None
                        at = offset + i
                        if runs and runs[-1][0] + len(runs[-1][1]) == at:
                            runs[-1][1].append(x)
                        else:
                            runs.append((at, bytearray([x])))
            offset += len(ba)
    return [(o, bytes(r)) for o, r in runs]


def stream_hashes(path: Path) -> Optional[str]:
    """ffmpeg's per-stream SHA-256 of the demuxed packets, or None without ffmpeg."""
    if not shutil.which("ffmpeg"):
        return None
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0", "-c", "copy",
         "-f", "streamhash", "-hash", "sha256", "-"],
        capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 and r.stdout.strip() else None


def apply_patch(data: bytes, runs: List[List]) -> bytes:
    buf = bytearray(data)
    for offset, hex_bytes in runs:
        orig = bytes.fromhex(hex_bytes)
        buf[offset : offset + len(orig)] = orig
    return bytes(buf)


def to_trash(path: Path, stamp: str) -> Path:
    TRASH.mkdir(exist_ok=True)
    dest = TRASH / f"{path.name}-{stamp}"
    shutil.move(str(path), str(dest))
    return dest


# --------------------------------------------------------------------------- #
# The plan: computed read-only, executed by apply()
# --------------------------------------------------------------------------- #
@dataclass
class Plan:
    archives: Path
    unzip: List[Tuple[Path, Path]] = field(default_factory=list)   # zip -> new folder
    rename: List[Tuple[Path, Path]] = field(default_factory=list)  # folder -> new name
    zips_to_verify: List[Tuple[Path, Path]] = field(default_factory=list)  # zip -> folder (final name)
    problems: List[str] = field(default_factory=list)

    def final_folders(self) -> List[Path]:
        names = set()
        for src in discover_sources(self.archives):
            if src.kind == "archive_dir":
                names.add(self.archives / canonical_name(src))
        names.update(dest for _, dest in self.unzip)
        return sorted(names)


def make_plan(archives: Path) -> Plan:
    plan = Plan(archives)
    sources = discover_sources(archives)
    dirs: Dict[str, Path] = {}
    for src in sources:
        if src.kind != "archive_dir":
            continue
        gen = generation_date(src)
        if gen in dirs:
            plan.problems.append(f"two folders for {gen}: {dirs[gen].name}, {src.path.name}")
            continue
        dirs[gen] = src.path
        want = archives / canonical_name(src)
        if src.path != want:
            if want.exists():
                plan.problems.append(f"cannot rename {src.path.name}: {want.name} exists")
            plan.rename.append((src.path, want))
    for src in sources:
        if src.kind != "archive_zip":
            continue
        gen = generation_date(src)
        want = archives / canonical_name(src)
        if gen in dirs:
            plan.zips_to_verify.append((src.path, want))
        elif want.exists():
            plan.problems.append(f"{want.name} exists but has a different generationDate")
        else:
            plan.unzip.append((src.path, want))
            plan.zips_to_verify.append((src.path, want))
            dirs[gen] = want
    return plan


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #
def preflight(plan: Plan) -> None:
    if plan.problems:
        raise ConsolidationError("plan has problems:\n  " + "\n  ".join(plan.problems))
    try:
        plan.archives.resolve().relative_to(REPO_ROOT)
        inside_repo = True
    except ValueError:
        inside_repo = False
    if inside_repo:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(plan.archives)])
        if r.returncode != 0:
            raise ConsolidationError("archives/ is NOT gitignored; refusing to touch it")
    need = sum(sum(i.file_size for i in zipfile.ZipFile(z).infolist()) for z, _ in plan.unzip)
    free = shutil.disk_usage(plan.archives).free
    if need * 1.1 > free:
        raise ConsolidationError(f"need ~{need >> 20} MB free to unzip, have {free >> 20} MB")


def safe_unzip(zip_path: Path, dest: Path) -> None:
    """Extract keeping each entry's timestamp; refuse paths that escape dest."""
    tmp = dest.with_name(dest.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(mode=0o700)
    root = tmp.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = (tmp / info.filename).resolve()
            if root != target and root not in target.parents:
                raise ConsolidationError(f"{zip_path.name}: unsafe path {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)
            ts = time.mktime(info.date_time + (0, 0, -1))
            os.utime(target, (ts, ts))
    zs = zip_path.stat().st_mtime
    os.utime(tmp, (zs, zs))
    tmp.rename(dest)


def verify_against_zip(zip_path: Path, folder: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        entries = {i.filename: i for i in zf.infolist() if not i.is_dir()}
    files = export_files(folder)
    only_zip = sorted(set(entries) - set(files))
    only_dir = sorted(set(files) - set(entries))
    if only_zip or only_dir:
        raise ConsolidationError(
            f"{zip_path.name} vs {folder.name}: only in zip {only_zip[:5]}, only in folder {only_dir[:5]}"
        )
    for rel, info in entries.items():
        p = files[rel]
        if p.stat().st_size != info.file_size or crc32_file(p) != info.CRC:
            raise ConsolidationError(f"{zip_path.name}: {rel} differs from {folder.name}")


def checksums_dir(archives: Path) -> Path:
    return archives / "checksums"


def write_checksums(archives: Path, folders: List[Path]) -> Dict[str, Dict[str, str]]:
    """Record every original file's SHA-256. Existing checksum files are kept:
    they describe the originals, which a deduplicated tree no longer holds."""
    out_dir = checksums_dir(archives)
    out_dir.mkdir(mode=0o700, exist_ok=True)
    sums: Dict[str, Dict[str, str]] = {}
    for folder in folders:
        f = out_dir / f"{folder.name}.sha256"
        if f.exists():
            sums[folder.name] = read_checksums(f)
            continue
        sums[folder.name] = {rel: sha256_file(p) for rel, p in export_files(folder).items()}
        tmp = f.with_suffix(".tmp")
        tmp.write_text("".join(f"{h}  {rel}\n" for rel, h in sorted(sums[folder.name].items())))
        tmp.chmod(0o400)
        tmp.rename(f)
    return sums


def read_checksums(path: Path) -> Dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        h, rel = line.split("  ", 1)
        out[rel] = h
    return out


def load_patches(archives: Path) -> dict:
    f = checksums_dir(archives) / "media-patches.json"
    return json.loads(f.read_text()) if f.exists() else {}


def find_near_duplicates(
    archives: Path, folders: List[Path], sums: Dict[str, Dict[str, str]]
) -> Tuple[Dict[str, dict], List[str]]:
    """For each older video that is a metadata-only variant of the newest
    export's copy: key "export/rel" -> patch record. Plus notes on rejects."""
    patches: Dict[str, dict] = {}
    notes: List[str] = []
    newest_first = sorted(folders, key=lambda p: p.name, reverse=True)
    # rel -> (folder, sha) of the newest copy of each video path
    newest: Dict[str, Tuple[Path, str]] = {}
    for folder in newest_first:
        for rel, h in sums[folder.name].items():
            if Path(rel).suffix.lower() in VIDEO_SUFFIXES and rel not in newest:
                newest[rel] = (folder, h)
    for folder in newest_first:
        for rel, h in sums[folder.name].items():
            if rel not in newest:
                continue
            ref_folder, ref_sha = newest[rel]
            if ref_folder == folder or h == ref_sha:
                continue
            mine, ref = folder / rel, ref_folder / rel
            runs = diff_runs(mine, ref, MAX_PATCH_BYTES)
            if runs is None:
                notes.append(f"kept: {folder.name}/{rel} (size differs or >{MAX_PATCH_BYTES} bytes differ)")
                continue
            moov = mp4_box_range(ref)
            if not moov or any(not (moov[0] <= o and o + len(b) <= moov[1]) for o, b in runs):
                notes.append(f"kept: {folder.name}/{rel} (a differing byte is outside the moov header)")
                continue
            sa, sb = stream_hashes(mine), stream_hashes(ref)
            if sa is None or sb is None or sa != sb:
                why = "ffmpeg unavailable" if not shutil.which("ffmpeg") else "stream hashes differ"
                notes.append(f"kept: {folder.name}/{rel} ({why})")
                continue
            patches[f"{folder.name}/{rel}"] = {
                "original_sha256": h,
                "replaced_by": f"{ref_folder.name}/{rel}",
                "replaced_by_sha256": ref_sha,
                "stream_sha256": sa.strip().splitlines(),
                "runs": [[o, b.hex()] for o, b in runs],
            }
    return patches, notes


def dedupe(
    folders: List[Path], sums: Dict[str, Dict[str, str]], patches: Dict[str, dict], dry_run: bool
) -> Tuple[int, int]:
    """Hardlink every file to one inode per target content. Returns (links, bytes saved)."""
    groups: Dict[str, List[Tuple[Path, str]]] = defaultdict(list)
    for folder in folders:
        for rel, h in sums[folder.name].items():
            patch = patches.get(f"{folder.name}/{rel}")
            target = patch["replaced_by_sha256"] if patch else h
            groups[target].append((folder / rel, h))
    links = saved = 0
    for target, members in groups.items():
        # Keeper: a file whose own content is the target, newest export first.
        originals = sorted((p for p, h in members if h == target), key=lambda p: str(p), reverse=True)
        if not originals:
            continue
        keeper = originals[0]
        k = keeper.stat()
        for path, _ in members:
            st = path.stat()
            if (st.st_dev, st.st_ino) == (k.st_dev, k.st_ino):
                continue
            links += 1
            saved += st.st_size
            if dry_run:
                continue
            tmp = path.with_name(path.name + ".linktmp")
            if tmp.exists():
                tmp.unlink()
            os.link(keeper, tmp)
            os.replace(tmp, path)
        if not dry_run:
            mode = keeper.stat().st_mode
            keeper.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return links, saved


def verify(archives: Path) -> List[str]:
    """Every file of every export hashes to its recorded original SHA-256,
    directly or after applying its patch. Returns failures (empty = pass)."""
    failures: List[str] = []
    patches = load_patches(archives)
    cache: Dict[Tuple[int, int], str] = {}
    sum_files = sorted(checksums_dir(archives).glob("*.sha256"))
    if not sum_files:
        return ["no checksum files in archives/checksums/"]
    for sf in sum_files:
        folder = archives / sf.name[: -len(".sha256")]
        if not folder.is_dir():
            failures.append(f"{folder.name}: folder missing")
            continue
        recorded = read_checksums(sf)
        present = export_files(folder)
        for rel in sorted(set(present) - set(recorded)):
            failures.append(f"{folder.name}/{rel}: not in checksums")
        for rel, want in recorded.items():
            p = present.get(rel)
            if p is None:
                failures.append(f"{folder.name}/{rel}: missing")
                continue
            st = p.stat()
            key = (st.st_dev, st.st_ino)
            if key not in cache:
                cache[key] = sha256_file(p)
            have = cache[key]
            if have == want:
                continue
            patch = patches.get(f"{folder.name}/{rel}")
            if patch and have == patch["replaced_by_sha256"]:
                rebuilt = apply_patch(p.read_bytes(), patch["runs"])
                if hashlib.sha256(rebuilt).hexdigest() == want:
                    continue
            failures.append(f"{folder.name}/{rel}: content does not match its original")
    return failures


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_plan(archives: Path) -> int:
    plan = make_plan(archives)
    for z, d in plan.unzip:
        print(f"unzip   {z.name} -> {d.name}/")
    for a, b in plan.rename:
        print(f"rename  {a.name}/ -> {b.name}/")
    for z, d in plan.zips_to_verify:
        print(f"verify  {z.name} == {d.name}/, then move the zip to the Trash")
    for p in plan.problems:
        print(f"PROBLEM {p}")
    zip_bytes = sum(z.stat().st_size for z, _ in plan.zips_to_verify)
    # Exact-duplicate estimate over existing folders (the unzipped ones aren't on disk yet).
    seen: Dict[str, int] = {}
    total = dup = 0
    for src in discover_sources(archives):
        if src.kind != "archive_dir":
            continue
        for rel, p in export_files(src.path).items():
            size = p.stat().st_size
            total += size
            h = sha256_file(p)
            if h in seen:
                dup += size
            seen[h] = size
    print(f"\nzips to remove:              {zip_bytes / 1e9:.2f} GB")
    print(f"exact duplicates in folders: {dup / 1e9:.2f} GB of {total / 1e9:.2f} GB")
    print("(near-duplicate videos are checked during apply; see media-patches.json)")
    return 1 if plan.problems else 0


def cmd_apply(archives: Path, trash: bool = True) -> int:
    plan = make_plan(archives)
    preflight(plan)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for z, d in plan.unzip:
        print(f"unzip   {z.name} -> {d.name}/")
        safe_unzip(z, d)
    for a, b in plan.rename:
        print(f"rename  {a.name}/ -> {b.name}/")
        a.rename(b)
    for z, d in plan.zips_to_verify:
        print(f"verify  {z.name} == {d.name}/")
        verify_against_zip(z, d)
    folders = [s.path for s in discover_sources(archives) if s.kind == "archive_dir"]
    print(f"hash    {len(folders)} exports -> checksums/")
    sums = write_checksums(archives, folders)

    patches = load_patches(archives)
    new, notes = find_near_duplicates(archives, folders, sums)
    for n in notes:
        print(f"        {n}")
    if new:
        patches.update(new)
        f = checksums_dir(archives) / "media-patches.json"
        if f.exists():
            f.chmod(0o600)
        f.write_text(json.dumps(patches, indent=2, sort_keys=True) + "\n")
        f.chmod(0o400)
    print(f"near-dup {len(new)} videos are metadata-only variants (patches recorded)")

    links, saved = dedupe(folders, sums, patches, dry_run=False)
    print(f"link    {links} files -> {saved / 1e9:.2f} GB freed")

    failures = verify(archives)
    if failures:
        raise ConsolidationError("verify failed; zips kept:\n  " + "\n  ".join(failures[:20]))
    print("verify  all files match their original SHA-256")

    if trash:
        for z, _ in plan.zips_to_verify:
            print(f"trash   {z.name} -> {to_trash(z, stamp).name}")
    return 0


def cmd_verify(archives: Path) -> int:
    failures = verify(archives)
    for f in failures:
        print(f"FAIL {f}")
    if not failures:
        n = sum(len(read_checksums(f)) for f in checksums_dir(archives).glob("*.sha256"))
        print(f"OK: {n} files across all exports match their original SHA-256")
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["plan", "apply", "verify"])
    ap.add_argument("--archives", type=Path, default=ARCHIVES_DIR)
    args = ap.parse_args(argv)
    try:
        if args.command == "plan":
            return cmd_plan(args.archives)
        if args.command == "apply":
            return cmd_apply(args.archives)
        return cmd_verify(args.archives)
    except ConsolidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
