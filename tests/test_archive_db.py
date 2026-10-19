"""Tests for src/archive_db.py — the snapshot database built from archives/.

Everything except the last section runs on small synthetic exports written to
tmp_path, so the suite is offline and needs no real archive. The last section
cross-checks a build of the real archives/ against their manifests and is
skipped on a fresh clone.
"""

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from src import archive_db as adb

ME = "1000"
# Synthetic Snowflake tweet IDs (2024-2025), so created_at is derivable.
T1, T2, T3 = "1873338172830646272", "1885659360261046272", "1995462883537846272"


# --------------------------------------------------------------------------- #
# Synthetic exports
# --------------------------------------------------------------------------- #
WRAPPER = {
    "follower": "follower",
    "following": "following",
    "block": "blocking",
    "mute": "muting",
    "like": "like",
}


def _files(
    generated_at,
    followers=(),
    following=(),
    blocks=(),
    mutes=(),
    likes=(),
    partial=False,
    split_likes=False,
    manifest_like_count=None,
):
    """Return {relative path: text} for one export."""
    payloads = {
        "follower": [{"accountId": a, "userLink": f"u/{a}"} for a in followers],
        "following": [{"accountId": a, "userLink": f"u/{a}"} for a in following],
        "block": [{"accountId": a, "userLink": f"u/{a}"} for a in blocks],
        "mute": [{"accountId": a} for a in mutes],
        "like": [
            {"tweetId": t, "fullText": txt, "expandedUrl": f"https://x.com/i/{t}"}
            for t, txt in likes
        ],
    }
    files, data_types = {}, {}
    for dtype, rows in payloads.items():
        wrapped = [{WRAPPER[dtype]: r} for r in rows]
        parts = (
            [wrapped[: len(wrapped) // 2], wrapped[len(wrapped) // 2 :]]
            if (dtype == "like" and split_likes)
            else [wrapped]
        )
        specs = []
        for i, part in enumerate(parts):
            name = f"data/{dtype}.js" if i == 0 else f"data/{dtype}-part{i + 1}.js"
            files[name] = f"window.YTD.{dtype}.part{i} = " + json.dumps(part, indent=2)
            specs.append(
                {
                    "fileName": name,
                    "globalName": f"YTD.{dtype}.part{i}",
                    "count": str(len(part)),
                }
            )
        if dtype == "like" and manifest_like_count is not None:
            specs[0]["count"] = str(manifest_like_count)
        data_types[dtype] = {"files": specs}
    manifest = {
        "userInfo": {"accountId": ME, "userName": "me", "displayName": "Me"},
        "archiveInfo": {"generationDate": generated_at, "isPartialArchive": partial},
        "dataTypes": data_types,
    }
    files["data/manifest.js"] = "window.__THAR_CONFIG = " + json.dumps(
        manifest, indent=2
    )
    return files


def make_dir(root: Path, name: str, **kw) -> Path:
    base = root / name
    for rel, text in _files(**kw).items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text)
    return base


def make_zip(root: Path, name: str, **kw) -> Path:
    path = root / name
    with zipfile.ZipFile(path, "w") as zf:
        for rel, text in _files(**kw).items():
            zf.writestr(rel, text)
    return path


@pytest.fixture
def archives(tmp_path):
    d = tmp_path / "archives"
    d.mkdir()
    return d


@pytest.fixture
def db(tmp_path):
    return tmp_path / "archive.db"


def build_and_open(db, archives, **kw):
    results = adb.build(db, archives, **kw)
    conn = adb.connect(db)
    return results, conn


def scalar(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


# --------------------------------------------------------------------------- #
# Reading exports
# --------------------------------------------------------------------------- #
def test_discover_finds_dirs_and_zips_only(archives):
    make_dir(
        archives, "twitter-archive-2025-01-01", generated_at="2025-01-01T00:00:00Z"
    )
    make_zip(archives, "twitter-2025-02-01.zip", generated_at="2025-02-01T00:00:00Z")
    (archives / "screenshots").mkdir()  # no manifest
    (archives / "notes.zip").write_bytes(b"not a zip")  # not a zip
    with zipfile.ZipFile(archives / "other.zip", "w") as zf:  # zip, but no manifest
        zf.writestr("readme.txt", "hi")
    found = {s.path.name: s.kind for s in adb.discover_sources(archives)}
    assert found == {
        "twitter-archive-2025-01-01": "archive_dir",
        "twitter-2025-02-01.zip": "archive_zip",
    }


def test_discover_missing_archives_dir_is_empty(tmp_path):
    assert adb.discover_sources(tmp_path / "nope") == []


def test_zip_and_dir_read_identically(archives):
    kw = dict(
        generated_at="2025-01-01T00:00:00Z", followers=["1", "2"], likes=[(T1, "a")]
    )
    d = adb.ArchiveSource(make_dir(archives, "d", **kw))
    z = adb.ArchiveSource(make_zip(archives, "z.zip", **kw))
    assert d.manifest() == z.manifest()
    assert d.read_ytd("data/like.js") == z.read_ytd("data/like.js")


def test_read_type_joins_part_files(archives):
    likes = [(T1, "a"), (T2, "b"), (T3, "c")]
    src = adb.ArchiveSource(
        make_dir(
            archives,
            "d",
            generated_at="2025-01-01T00:00:00Z",
            likes=likes,
            split_likes=True,
        )
    )
    rows = adb.read_type(src, src.manifest(), "like")
    assert [r["tweetId"] for r in rows] == [T1, T2, T3]


def test_read_type_unwraps_each_entry(archives):
    src = adb.ArchiveSource(
        make_dir(
            archives,
            "d",
            generated_at="2025-01-01T00:00:00Z",
            blocks=["7"],
            mutes=["8"],
        )
    )
    m = src.manifest()
    assert adb.read_type(src, m, "block") == [{"accountId": "7", "userLink": "u/7"}]
    assert adb.read_type(src, m, "mute") == [{"accountId": "8"}]


def test_read_type_absent_type_is_empty(archives):
    src = adb.ArchiveSource(
        make_dir(archives, "d", generated_at="2025-01-01T00:00:00Z")
    )
    assert adb.read_type(src, src.manifest(), "bookmark") == []


def test_read_type_count_mismatch_raises(archives):
    src = adb.ArchiveSource(
        make_dir(
            archives,
            "d",
            generated_at="2025-01-01T00:00:00Z",
            likes=[(T1, "a")],
            manifest_like_count=2,
        )
    )
    with pytest.raises(adb.ArchiveError, match="like has 1 entries, manifest says 2"):
        adb.read_type(src, src.manifest(), "like")


def test_snowflake_to_iso():
    # The top 41 bits count ms since Twitter's epoch, 2010-11-04T01:42:54.657Z.
    assert adb.snowflake_to_iso(str(1 << 22)) == "2010-11-04T01:42:54.658000+00:00"
    # The low 22 bits (worker, sequence) don't move the time.
    one_day_ms = 86_400_000
    assert (
        adb.snowflake_to_iso(str((one_day_ms << 22) | 0x3FFFFF))
        == "2010-11-05T01:42:54.657000+00:00"
    )
    assert adb.snowflake_to_iso(T1).startswith("2024-12-29")
    assert adb.snowflake_to_iso("12345") is None  # pre-2010 sequential ID


# --------------------------------------------------------------------------- #
# Building
# --------------------------------------------------------------------------- #
def test_build_records_snapshot_metadata(archives, db):
    make_dir(archives, "a", generated_at="2025-01-01T00:00:00Z", followers=["1"])
    _, conn = build_and_open(db, archives)
    row = conn.execute("SELECT * FROM snapshots").fetchone()
    assert row["generated_at"] == "2025-01-01T00:00:00Z"
    assert row["account_id"] == ME
    assert row["source_kind"] == "archive_dir"
    assert row["is_partial"] == 0
    assert row["source_path"].endswith("a")
    assert scalar(conn, "SELECT value FROM meta WHERE key='schema_version'") == str(
        adb.SCHEMA_VERSION
    )


def test_build_stores_every_relation(archives, db):
    make_dir(
        archives,
        "a",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1", "2"],
        following=["3"],
        blocks=["4"],
        mutes=["5", "6"],
        likes=[(T1, "x")],
    )
    _, conn = build_and_open(db, archives)
    counts = dict(
        conn.execute(
            "SELECT relation, COUNT(*) FROM snapshot_accounts GROUP BY relation"
        ).fetchall()
    )
    assert counts == {"follower": 2, "following": 1, "block": 1, "mute": 2}
    assert scalar(conn, "SELECT COUNT(*) FROM saves WHERE kind='like'") == 1
    t = conn.execute("SELECT * FROM tweets").fetchone()
    assert (t["tweet_id"], t["full_text"], t["created_at"][:10]) == (
        T1,
        "x",
        "2024-12-29",
    )


def test_build_is_idempotent(archives, db):
    make_dir(
        archives,
        "a",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1"],
        likes=[(T1, "x")],
    )
    first = adb.build(db, archives)
    second = adb.build(db, archives)
    assert first[0][1] == "snapshot 1"
    assert second[0][1] == "skipped (already ingested)"
    conn = adb.connect(db)
    assert scalar(conn, "SELECT COUNT(*) FROM snapshots") == 1
    assert scalar(conn, "SELECT COUNT(*) FROM snapshot_accounts") == 1
    assert scalar(conn, "SELECT COUNT(*) FROM tweets") == 1


def test_build_picks_up_new_export(archives, db):
    make_dir(archives, "a", generated_at="2025-01-01T00:00:00Z", followers=["1"])
    adb.build(db, archives)
    make_zip(
        archives, "b.zip", generated_at="2025-02-01T00:00:00Z", followers=["1", "2"]
    )
    results = adb.build(db, archives)
    assert ("b.zip", "snapshot 2") in results


def test_same_export_as_dir_and_zip_is_read_from_dir(archives, db):
    kw = dict(generated_at="2025-01-01T00:00:00Z", followers=["1"])
    make_zip(archives, "a.zip", **kw)  # sorts first by name
    make_dir(archives, "z-folder", **kw)
    results, conn = build_and_open(db, archives)
    assert scalar(conn, "SELECT COUNT(*) FROM snapshots") == 1
    assert scalar(conn, "SELECT source_kind FROM snapshots") == "archive_dir"
    assert dict(results)["a.zip"] == "skipped (already ingested)"


def test_rebuild_starts_from_empty(archives, db):
    make_dir(archives, "a", generated_at="2025-01-01T00:00:00Z", followers=["1"])
    adb.build(db, archives)
    adb.connect(db).execute(
        "INSERT INTO meta VALUES ('marker', 'x')"
    ).connection.commit()
    adb.build(db, archives, rebuild=True)
    conn = adb.connect(db)
    assert conn.execute("SELECT 1 FROM meta WHERE key='marker'").fetchone() is None
    assert scalar(conn, "SELECT COUNT(*) FROM snapshots") == 1


def test_bad_export_writes_nothing(archives, db):
    make_dir(
        archives,
        "bad",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1"],
        likes=[(T1, "x")],
        manifest_like_count=5,
    )
    with pytest.raises(adb.ArchiveError):
        adb.build(db, archives)
    conn = adb.connect(db)
    for table in ("snapshots", "snapshot_accounts", "tweets", "saves"):
        assert scalar(conn, f"SELECT COUNT(*) FROM {table}") == 0, table


def test_duplicate_ids_in_one_export_are_collapsed(archives, db):
    make_dir(
        archives,
        "a",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1", "1"],
        likes=[(T1, "x"), (T1, "x")],
    )
    _, conn = build_and_open(db, archives)
    assert scalar(conn, "SELECT COUNT(*) FROM snapshot_accounts") == 1
    assert scalar(conn, "SELECT COUNT(*) FROM saves") == 1


def test_foreign_keys_enforced(db):
    conn = adb.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO snapshot_accounts VALUES (99, 'follower', '1')")


def test_relation_check_constraint(archives, db):
    make_dir(archives, "a", generated_at="2025-01-01T00:00:00Z")
    _, conn = build_and_open(db, archives)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO snapshot_accounts VALUES (1, 'friend', '1')")


# --------------------------------------------------------------------------- #
# Tweet text: newest snapshot wins
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("newest_first", [False, True])
def test_newest_snapshot_text_wins(archives, db, newest_first):
    old = dict(generated_at="2025-01-01T00:00:00Z", likes=[(T1, "old text")])
    new = dict(generated_at="2025-06-01T00:00:00Z", likes=[(T1, "new text")])
    # Ingest order follows file names within a kind; swap names to swap order.
    make_dir(archives, "b" if newest_first else "a", **old)
    make_dir(archives, "a" if newest_first else "b", **new)
    _, conn = build_and_open(db, archives)
    assert (
        scalar(conn, "SELECT full_text FROM tweets WHERE tweet_id=?", T1) == "new text"
    )


# --------------------------------------------------------------------------- #
# Views: account_changes, saved_tweets
# --------------------------------------------------------------------------- #
def changes(conn, relation="follower"):
    return sorted(
        (r["until"], r["account_id"], r["change"])
        for r in conn.execute(
            "SELECT * FROM account_changes WHERE relation=?", (relation,)
        )
    )


def test_account_changes_between_consecutive_snapshots(archives, db):
    make_dir(archives, "s1", generated_at="2025-01-01T00:00:00Z", followers=["1", "2"])
    make_dir(archives, "s2", generated_at="2025-02-01T00:00:00Z", followers=["2", "3"])
    make_dir(
        archives, "s3", generated_at="2025-03-01T00:00:00Z", followers=["2", "3", "1"]
    )
    _, conn = build_and_open(db, archives)
    assert changes(conn) == [
        ("2025-02-01T00:00:00Z", "1", "removed"),
        ("2025-02-01T00:00:00Z", "3", "added"),
        ("2025-03-01T00:00:00Z", "1", "added"),  # re-follow shows up again
    ]
    row = conn.execute(
        "SELECT since FROM account_changes WHERE account_id='3'"
    ).fetchone()
    assert row["since"] == "2025-01-01T00:00:00Z"


def test_account_changes_ignore_ingest_order(archives, db):
    # Names sort opposite to dates: pairs must follow generated_at, not snapshot id.
    make_dir(archives, "z-old", generated_at="2025-01-01T00:00:00Z", followers=["1"])
    make_dir(archives, "a-new", generated_at="2025-02-01T00:00:00Z", followers=["2"])
    _, conn = build_and_open(db, archives)
    assert changes(conn) == [
        ("2025-02-01T00:00:00Z", "1", "removed"),
        ("2025-02-01T00:00:00Z", "2", "added"),
    ]


def test_account_changes_are_per_relation(archives, db):
    make_dir(
        archives,
        "s1",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1"],
        following=["1"],
    )
    make_dir(
        archives,
        "s2",
        generated_at="2025-02-01T00:00:00Z",
        followers=["1"],
        following=[],
    )
    _, conn = build_and_open(db, archives)
    assert changes(conn, "follower") == []
    assert changes(conn, "following") == [("2025-02-01T00:00:00Z", "1", "removed")]


def test_single_snapshot_has_no_changes(archives, db):
    make_dir(archives, "s1", generated_at="2025-01-01T00:00:00Z", followers=["1"])
    _, conn = build_and_open(db, archives)
    assert changes(conn) == []


def test_partial_snapshots_are_left_out_of_changes(archives, db):
    make_dir(archives, "s1", generated_at="2025-01-01T00:00:00Z", followers=["1", "2"])
    make_dir(
        archives, "s2", generated_at="2025-02-01T00:00:00Z", followers=[], partial=True
    )
    make_dir(archives, "s3", generated_at="2025-03-01T00:00:00Z", followers=["1", "2"])
    _, conn = build_and_open(db, archives)
    assert changes(conn) == []  # s1 -> s3 directly, nobody changed


def test_change_summary_counts(archives, db):
    make_dir(
        archives, "s1", generated_at="2025-01-01T00:00:00Z", followers=["1", "2", "3"]
    )
    make_dir(archives, "s2", generated_at="2025-02-01T00:00:00Z", followers=["3", "4"])
    _, conn = build_and_open(db, archives)
    [row] = adb.change_summary(conn, "follower")
    assert (row["added"], row["removed"]) == (1, 2)


def test_saved_tweets_first_last_seen(archives, db):
    make_dir(
        archives,
        "s1",
        generated_at="2025-01-01T00:00:00Z",
        likes=[(T1, "a"), (T2, "b")],
    )
    make_dir(
        archives,
        "s2",
        generated_at="2025-02-01T00:00:00Z",
        likes=[(T2, "b"), (T3, "c")],
    )
    _, conn = build_and_open(db, archives)
    rows = {r["tweet_id"]: r for r in conn.execute("SELECT * FROM saved_tweets")}
    assert set(rows) == {T1, T2, T3}  # the unliked T1 is kept
    assert (rows[T1]["first_seen"], rows[T1]["last_seen"], rows[T1]["still_saved"]) == (
        "2025-01-01T00:00:00Z",
        "2025-01-01T00:00:00Z",
        0,
    )
    assert (rows[T2]["first_seen"], rows[T2]["still_saved"]) == (
        "2025-01-01T00:00:00Z",
        1,
    )
    assert (rows[T3]["first_seen"], rows[T3]["still_saved"]) == (
        "2025-02-01T00:00:00Z",
        1,
    )


# --------------------------------------------------------------------------- #
# Full-text search
# --------------------------------------------------------------------------- #
@pytest.fixture
def search_db(archives, db):
    make_dir(
        archives,
        "s1",
        generated_at="2025-01-01T00:00:00Z",
        likes=[
            (T1, "Collection of fun facts about SQLite"),
            (T2, "Running Postgres indexes in production"),
            (T3, "Café culture and naïve résumé writing"),
        ],
    )
    _, conn = build_and_open(db, archives)
    return conn


def ids(rows):
    return [r["tweet_id"] for r in rows]


def test_search_keyword(search_db):
    assert ids(adb.search(search_db, "sqlite")) == [T1]


def test_search_is_case_insensitive(search_db):
    assert ids(adb.search(search_db, "SQLITE")) == [T1]


def test_search_stems_words(search_db):
    assert ids(adb.search(search_db, "run index")) == [T2]  # porter: running, indexes


def test_search_ignores_diacritics(search_db):
    assert ids(adb.search(search_db, "cafe resume")) == [T3]


def test_search_phrase_prefix_and_boolean(search_db):
    assert ids(adb.search(search_db, '"fun facts"')) == [T1]
    assert ids(adb.search(search_db, "postg*")) == [T2]
    assert sorted(ids(adb.search(search_db, "sqlite OR postgres"))) == sorted([T1, T2])
    assert ids(adb.search(search_db, "sqlite NOT fun")) == []


def test_search_snippet_marks_match(search_db):
    [row] = adb.search(search_db, "sqlite")
    assert "[SQLite]" in row["snippet"]


def test_search_limit(search_db):
    assert len(adb.search(search_db, "sqlite OR postgres OR cafe", limit=2)) == 2


def test_fts_follows_text_updates(archives, db):
    make_dir(archives, "s1", generated_at="2025-01-01T00:00:00Z", likes=[(T1, "alpha")])
    adb.build(db, archives)
    make_dir(archives, "s2", generated_at="2025-02-01T00:00:00Z", likes=[(T1, "beta")])
    _, conn = build_and_open(db, archives)
    assert ids(adb.search(conn, "alpha")) == []
    assert ids(adb.search(conn, "beta")) == [T1]
    conn.execute("INSERT INTO tweets_fts(tweets_fts) VALUES ('integrity-check')")


def test_fts_follows_deletes(search_db):
    search_db.execute("DELETE FROM saves")
    search_db.execute("DELETE FROM tweets WHERE tweet_id=?", (T1,))
    assert ids(adb.search(search_db, "sqlite")) == []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
@pytest.fixture
def cli_db(archives, db):
    make_dir(
        archives,
        "s1",
        generated_at="2025-01-01T00:00:00Z",
        followers=["1"],
        likes=[(T1, "sqlite rocks")],
    )
    make_dir(
        archives,
        "s2",
        generated_at="2025-02-01T00:00:00Z",
        followers=["2"],
        likes=[(T1, "sqlite rocks")],
    )
    return db


def test_cli_build(cli_db, archives, capsys):
    assert adb.main(["--db", str(cli_db), "build", "--archives", str(archives)]) == 0
    out = capsys.readouterr().out
    assert out.count("snapshot ") == 2


def test_cli_stats_changes_search(cli_db, archives, capsys):
    adb.main(["--db", str(cli_db), "build", "--archives", str(archives)])
    capsys.readouterr()

    adb.main(["--db", str(cli_db), "stats"])
    out = capsys.readouterr().out
    assert "2025-02-01T00:00:00Z" in out and "followers" in out

    adb.main(["--db", str(cli_db), "changes"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[1].split()[-2:] == ["1", "1"]  # one added, one removed

    adb.main(["--db", str(cli_db), "search", "sqlite"])
    assert "[sqlite]" in capsys.readouterr().out


def test_cli_rejects_unknown_relation(cli_db):
    with pytest.raises(SystemExit):
        adb.main(["--db", str(cli_db), "changes", "--relation", "friend"])


# --------------------------------------------------------------------------- #
# Against the real archives/ (skipped on a fresh clone)
# --------------------------------------------------------------------------- #
REAL = adb.ARCHIVES_DIR
has_real = pytest.mark.skipif(
    not adb.discover_sources(REAL), reason="no local archives/"
)


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("real") / "archive.db"
    adb.build(path, REAL)
    return adb.connect(path)


@has_real
def test_real_every_distinct_export_is_ingested(real_db):
    dates = {
        s.manifest()["archiveInfo"]["generationDate"]
        for s in adb.discover_sources(REAL)
    }
    assert scalar(real_db, "SELECT COUNT(*) FROM snapshots") == len(dates)


@has_real
def test_real_counts_match_manifests(real_db):
    for src in adb.discover_sources(REAL):
        m = src.manifest()
        sid = scalar(
            real_db,
            "SELECT id FROM snapshots WHERE generated_at=?",
            m["archiveInfo"]["generationDate"],
        )
        for dtype, relation in adb.ACCOUNT_TYPES.items():
            want = len({r["accountId"] for r in adb.read_type(src, m, dtype)})
            got = scalar(
                real_db,
                "SELECT COUNT(*) FROM snapshot_accounts "
                "WHERE snapshot_id=? AND relation=?",
                sid,
                relation,
            )
            assert got == want, (src.path.name, dtype)


@has_real
def test_real_changes_reconcile_with_totals(real_db):
    """For every consecutive pair: size(B) - size(A) == added - removed."""
    for relation in adb.ACCOUNT_TYPES.values():
        size = dict(
            real_db.execute(
                "SELECT sn.generated_at, COUNT(a.account_id) FROM snapshots sn "
                "LEFT JOIN snapshot_accounts a ON a.snapshot_id = sn.id AND a.relation = ? "
                "GROUP BY sn.id",
                (relation,),
            ).fetchall()
        )
        for r in adb.change_summary(real_db, relation):
            assert (
                size[r["until"]] - size[r["since"]] == r["added"] - r["removed"]
            ), relation


@has_real
def test_real_every_tweet_is_searchable(real_db):
    real_db.execute("INSERT INTO tweets_fts(tweets_fts) VALUES ('integrity-check')")
    n_fts = scalar(real_db, "SELECT COUNT(*) FROM tweets_fts")
    assert n_fts == scalar(real_db, "SELECT COUNT(*) FROM tweets") > 0
