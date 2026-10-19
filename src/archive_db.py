"""
Build `data/archive.db`: every X archive export under `archives/`, as snapshots.

Each export (unpacked folder or raw zip) becomes one row in `snapshots`, and its
full follower / following / block / mute / like lists are stored against it.
Follows, unfollows, and likes that appeared or disappeared are *derived* by
views comparing consecutive snapshots, so they can never go stale. Liked tweet
text is indexed with SQLite FTS5 for offline keyword search.

The database is built only from `archives/`, so deleting it and rebuilding
loses nothing.

Usage:
    python -m src.archive_db build            # ingest any export not yet in the db
    python -m src.archive_db build --rebuild  # delete the db and ingest everything
    python -m src.archive_db stats
    python -m src.archive_db changes [--relation follower]
    python -m src.archive_db search "query" [--limit 20]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVES_DIR = REPO_ROOT / "archives"
DB_PATH = REPO_ROOT / "data" / "archive.db"

SCHEMA_VERSION = 1

# manifest dataType -> relation stored in snapshot_accounts
ACCOUNT_TYPES = {
    "follower": "follower",
    "following": "following",
    "block": "block",
    "mute": "mute",
}

# 2010-11-04T01:42:54.657Z, the zero point of Snowflake timestamps.
TWITTER_EPOCH = datetime(2010, 11, 4, 1, 42, 54, 657000, tzinfo=timezone.utc)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per export. generated_at (from the export's manifest) is the
-- identity, so the same export as a folder and as a zip is ingested once.
CREATE TABLE IF NOT EXISTS snapshots (
    id           INTEGER PRIMARY KEY,
    generated_at TEXT NOT NULL UNIQUE,   -- archiveInfo.generationDate, ISO-8601 UTC
    account_id   TEXT NOT NULL,          -- whose archive this is
    source_path  TEXT NOT NULL,          -- relative to the repo root
    source_kind  TEXT NOT NULL CHECK (source_kind IN ('archive_dir', 'archive_zip')),
    is_partial   INTEGER NOT NULL,       -- archiveInfo.isPartialArchive
    ingested_at  TEXT NOT NULL
);

-- Full account lists per snapshot. IDs are TEXT: they exceed 2^53.
CREATE TABLE IF NOT EXISTS snapshot_accounts (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL CHECK (relation IN ('follower', 'following', 'block', 'mute')),
    account_id  TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, relation, account_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS snapshot_accounts_by_account
    ON snapshot_accounts (account_id, relation);

-- One row per distinct tweet ever liked. Text comes from the newest snapshot
-- that contained the tweet (text_snapshot_id).
CREATE TABLE IF NOT EXISTS tweets (
    tweet_id         TEXT PRIMARY KEY,
    full_text        TEXT,
    url              TEXT,
    created_at       TEXT,               -- derived from the Snowflake ID; NULL if pre-2010
    text_snapshot_id INTEGER NOT NULL REFERENCES snapshots(id)
);

-- Which snapshot contained which like. Room for 'bookmark' later (ROADMAP 2.7).
CREATE TABLE IF NOT EXISTS saves (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('like', 'bookmark')),
    tweet_id    TEXT NOT NULL REFERENCES tweets(tweet_id),
    PRIMARY KEY (snapshot_id, kind, tweet_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS saves_by_tweet ON saves (tweet_id, kind);

-- Keyword search over tweets.full_text. External-content table: the text is
-- stored once, in tweets; the triggers keep the index in sync.
CREATE VIRTUAL TABLE IF NOT EXISTS tweets_fts USING fts5 (
    full_text,
    content = 'tweets',
    content_rowid = 'rowid',
    tokenize = 'porter unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS tweets_fts_insert AFTER INSERT ON tweets BEGIN
    INSERT INTO tweets_fts (rowid, full_text) VALUES (new.rowid, new.full_text);
END;
CREATE TRIGGER IF NOT EXISTS tweets_fts_delete AFTER DELETE ON tweets BEGIN
    INSERT INTO tweets_fts (tweets_fts, rowid, full_text) VALUES ('delete', old.rowid, old.full_text);
END;
CREATE TRIGGER IF NOT EXISTS tweets_fts_update AFTER UPDATE OF full_text ON tweets BEGIN
    INSERT INTO tweets_fts (tweets_fts, rowid, full_text) VALUES ('delete', old.rowid, old.full_text);
    INSERT INTO tweets_fts (rowid, full_text) VALUES (new.rowid, new.full_text);
END;

-- Each complete snapshot next to the one before it. Partial exports are left
-- out: a missing file would read as everyone unfollowing.
CREATE VIEW IF NOT EXISTS snapshot_pairs AS
SELECT
    id                                          AS snapshot_id,
    generated_at,
    LAG(id)           OVER (ORDER BY generated_at) AS prev_snapshot_id,
    LAG(generated_at) OVER (ORDER BY generated_at) AS prev_generated_at
FROM snapshots
WHERE is_partial = 0;

-- Accounts that appeared in or disappeared from a relation between two
-- consecutive snapshots. relation='follower', change='removed' means an
-- unfollow OR a deactivated / suspended account; the archive can't tell.
CREATE VIEW IF NOT EXISTS account_changes AS
SELECT p.prev_generated_at AS since, p.generated_at AS until,
       cur.relation, cur.account_id, 'added' AS change
FROM snapshot_pairs p
JOIN snapshot_accounts cur ON cur.snapshot_id = p.snapshot_id
WHERE p.prev_snapshot_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM snapshot_accounts o
                  WHERE o.snapshot_id = p.prev_snapshot_id
                    AND o.relation = cur.relation AND o.account_id = cur.account_id)
UNION ALL
SELECT p.prev_generated_at, p.generated_at,
       old.relation, old.account_id, 'removed'
FROM snapshot_pairs p
JOIN snapshot_accounts old ON old.snapshot_id = p.prev_snapshot_id
WHERE NOT EXISTS (SELECT 1 FROM snapshot_accounts c
                  WHERE c.snapshot_id = p.snapshot_id
                    AND c.relation = old.relation AND c.account_id = old.account_id);

-- Every saved tweet with the first and last snapshot it appeared in.
-- still_saved = present in the newest snapshot.
CREATE VIEW IF NOT EXISTS saved_tweets AS
SELECT t.tweet_id, s.kind, t.full_text, t.url, t.created_at,
       MIN(sn.generated_at) AS first_seen,
       MAX(sn.generated_at) AS last_seen,
       MAX(sn.generated_at) = (SELECT MAX(generated_at) FROM snapshots) AS still_saved
FROM saves s
JOIN tweets t     ON t.tweet_id = s.tweet_id
JOIN snapshots sn ON sn.id = s.snapshot_id
GROUP BY t.tweet_id, s.kind;
"""


# --------------------------------------------------------------------------- #
# Reading exports
# --------------------------------------------------------------------------- #
class ArchiveError(Exception):
    """An export is unreadable or doesn't match its own manifest."""


@dataclass
class ArchiveSource:
    """One export on disk: an unpacked folder or a zip, read the same way."""

    path: Path

    @property
    def kind(self) -> str:
        return "archive_zip" if self.path.suffix == ".zip" else "archive_dir"

    def read_text(self, rel: str) -> str:
        if self.kind == "archive_zip":
            with zipfile.ZipFile(self.path) as zf:
                return zf.read(rel).decode("utf-8")
        return (self.path / rel).read_text(encoding="utf-8")

    def read_ytd(self, rel: str) -> list:
        """Parse a `window.YTD.<name>.partN = [...]` file."""
        text = self.read_text(rel)
        return json.loads(text[text.index("[") :])

    def manifest(self) -> dict:
        text = self.read_text("data/manifest.js")
        return json.loads(text[text.index("{") :])


def discover_sources(archives_dir: Path = ARCHIVES_DIR) -> List[ArchiveSource]:
    """Every folder or zip under archives/ with a data/manifest.js at its root."""
    found = []
    for p in sorted(archives_dir.iterdir()) if archives_dir.is_dir() else []:
        if p.is_dir() and (p / "data" / "manifest.js").is_file():
            found.append(ArchiveSource(p))
        elif p.suffix == ".zip" and zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as zf:
                if "data/manifest.js" in zf.namelist():
                    found.append(ArchiveSource(p))
    return found


def read_type(src: ArchiveSource, manifest: dict, data_type: str) -> List[dict]:
    """All entries of one data type across its part files, checked against the manifest."""
    spec = manifest["dataTypes"].get(data_type, {})
    entries: List[dict] = []
    expected = 0
    for f in spec.get("files", []):
        expected += int(f.get("count", 0))
        entries.extend(src.read_ytd(f["fileName"]))
    if len(entries) != expected:
        raise ArchiveError(
            f"{src.path.name}: {data_type} has {len(entries)} entries, manifest says {expected}"
        )
    # Each entry wraps its payload in one key: {"follower": {...}}, {"blocking": {...}}
    return [next(iter(e.values())) for e in entries]


def snowflake_to_iso(tweet_id: str) -> Optional[str]:
    """Tweet IDs since late 2010 carry their creation time in the top 41 bits."""
    n = int(tweet_id)
    if n < (1 << 22):
        return None
    return (TWITTER_EPOCH + timedelta(milliseconds=n >> 22)).isoformat()


# --------------------------------------------------------------------------- #
# Ingest
# --------------------------------------------------------------------------- #
def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    return conn


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def ingest_source(conn: sqlite3.Connection, src: ArchiveSource) -> Optional[int]:
    """Ingest one export in a single transaction. Returns the snapshot id, or
    None if an export with the same generation date is already in the db."""
    manifest = src.manifest()
    info = manifest["archiveInfo"]
    generated_at = info["generationDate"]
    if conn.execute(
        "SELECT 1 FROM snapshots WHERE generated_at = ?", (generated_at,)
    ).fetchone():
        return None

    # Read and validate everything before writing anything.
    accounts = {rel: read_type(src, manifest, t) for t, rel in ACCOUNT_TYPES.items()}
    likes = read_type(src, manifest, "like")

    with conn:
        cur = conn.execute(
            """INSERT INTO snapshots
               (generated_at, account_id, source_path, source_kind, is_partial, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                generated_at,
                manifest["userInfo"]["accountId"],
                _rel(src.path),
                src.kind,
                int(bool(info.get("isPartialArchive"))),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        sid = cur.lastrowid
        for relation, rows in accounts.items():
            conn.executemany(
                "INSERT OR IGNORE INTO snapshot_accounts VALUES (?, ?, ?)",
                ((sid, relation, r["accountId"]) for r in rows),
            )
        for like in likes:
            tid = like["tweetId"]
            # Newest snapshot wins the text, whatever order exports arrive in.
            conn.execute(
                """INSERT INTO tweets (tweet_id, full_text, url, created_at, text_snapshot_id)
                   VALUES (:tid, :text, :url, :created, :sid)
                   ON CONFLICT (tweet_id) DO UPDATE SET
                       full_text = excluded.full_text,
                       url = excluded.url,
                       text_snapshot_id = excluded.text_snapshot_id
                   WHERE (SELECT generated_at FROM snapshots WHERE id = excluded.text_snapshot_id)
                       > (SELECT generated_at FROM snapshots WHERE id = tweets.text_snapshot_id)""",
                {
                    "tid": tid,
                    "text": like.get("fullText"),
                    "url": like.get("expandedUrl"),
                    "created": snowflake_to_iso(tid),
                    "sid": sid,
                },
            )
            conn.execute(
                "INSERT OR IGNORE INTO saves VALUES (?, 'like', ?)", (sid, tid)
            )
    return sid


def build(
    db_path: Path = DB_PATH, archives_dir: Path = ARCHIVES_DIR, rebuild: bool = False
) -> List[Tuple[str, str]]:
    """Ingest every export not yet in the db. Returns (source, outcome) pairs."""
    if rebuild and db_path.exists():
        db_path.unlink()
    conn = connect(db_path)
    # Folders before zips, so an export present as both is read from the folder.
    sources = sorted(
        discover_sources(archives_dir), key=lambda s: s.kind != "archive_dir"
    )
    results = []
    for src in sources:
        sid = ingest_source(conn, src)
        results.append(
            (
                src.path.name,
                "skipped (already ingested)" if sid is None else f"snapshot {sid}",
            )
        )
    conn.close()
    return results


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def stats(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT sn.generated_at, sn.source_kind,
                  SUM(a.relation = 'follower')  AS followers,
                  SUM(a.relation = 'following') AS following,
                  SUM(a.relation = 'block')     AS blocks,
                  SUM(a.relation = 'mute')      AS mutes,
                  (SELECT COUNT(*) FROM saves s WHERE s.snapshot_id = sn.id AND s.kind = 'like') AS likes
           FROM snapshots sn
           LEFT JOIN snapshot_accounts a ON a.snapshot_id = sn.id
           GROUP BY sn.id ORDER BY sn.generated_at"""
    ).fetchall()


def change_summary(conn: sqlite3.Connection, relation: str) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT since, until, SUM(change = 'added') AS added, SUM(change = 'removed') AS removed
           FROM account_changes WHERE relation = ?
           GROUP BY since, until ORDER BY until""",
        (relation,),
    ).fetchall()


def search(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[sqlite3.Row]:
    """FTS5 query syntax: words, "exact phrase", OR, NOT, prefix*."""
    return conn.execute(
        """SELECT t.tweet_id, t.created_at, t.url,
                  snippet(tweets_fts, 0, '[', ']', '…', 16) AS snippet
           FROM tweets_fts JOIN tweets t ON t.rowid = tweets_fts.rowid
           WHERE tweets_fts MATCH ? ORDER BY bm25(tweets_fts) LIMIT ?""",
        (query, limit),
    ).fetchall()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m src.archive_db",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--db", type=Path, default=DB_PATH)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="ingest new exports from archives/")
    b.add_argument("--rebuild", action="store_true", help="delete the db first")
    b.add_argument("--archives", type=Path, default=ARCHIVES_DIR)
    sub.add_parser("stats", help="counts per snapshot")
    c = sub.add_parser("changes", help="added/removed accounts between snapshots")
    c.add_argument(
        "--relation", default="follower", choices=sorted(ACCOUNT_TYPES.values())
    )
    s = sub.add_parser("search", help="keyword search over liked tweets")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=20)
    args = ap.parse_args(argv)

    if args.cmd == "build":
        for name, outcome in build(args.db, args.archives, args.rebuild):
            print(f"{outcome:<28} {name}")
        return 0

    conn = connect(args.db)
    if args.cmd == "stats":
        print(
            f"{'snapshot':<26} {'source':<12} {'followers':>9} {'following':>9} "
            f"{'blocks':>6} {'mutes':>5} {'likes':>6}"
        )
        for r in stats(conn):
            print(
                f"{r['generated_at']:<26} {r['source_kind']:<12} {r['followers']:>9} "
                f"{r['following']:>9} {r['blocks']:>6} {r['mutes']:>5} {r['likes']:>6}"
            )
    elif args.cmd == "changes":
        print(f"{'since':<26} {'until':<26} {'added':>6} {'removed':>7}")
        for r in change_summary(conn, args.relation):
            print(
                f"{r['since']:<26} {r['until']:<26} {r['added']:>6} {r['removed']:>7}"
            )
    elif args.cmd == "search":
        for r in search(conn, args.query, args.limit):
            print(
                f"{(r['created_at'] or '')[:10]}  {r['snippet']}\n            {r['url']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
