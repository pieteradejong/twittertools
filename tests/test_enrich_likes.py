"""Unit tests for scripts/enrich_likes.py — no network, in-memory SQLite."""
import json
import sqlite3
import sys
from datetime import timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import enrich_likes as el  # noqa: E402


# Trimmed but structurally faithful syndication payload (video + photo + quote + reply).
FIXTURE_VIDEO = {
    "__typename": "Tweet",
    "id_str": "1928058740536246272",
    "text": "Starship update https://t.co/abc #SpaceX",
    "lang": "en",
    "created_at": "2025-05-29T21:04:11.000Z",
    "favorite_count": 1234,
    "conversation_count": 56,
    "possibly_sensitive": False,
    "user": {"id_str": "1001", "name": "Example Rockets", "screen_name": "example_rockets",
             "profile_image_url_https": "https://pbs.twimg.com/x.jpg", "verified": False, "is_blue_verified": True},
    "entities": {
        "hashtags": [{"text": "SpaceX"}],
        "urls": [{"url": "https://t.co/abc", "expanded_url": "https://rockets.example.com/launches"}],
        "user_mentions": [{"screen_name": "space_agency"}],
    },
    "mediaDetails": [
        {"type": "video", "media_url_https": "https://pbs.twimg.com/poster.jpg",
         "video_info": {"duration_millis": 32000, "variants": []}},
        {"type": "photo", "media_url_https": "https://pbs.twimg.com/photo.jpg"},
    ],
    "in_reply_to_screen_name": "someone",
    "in_reply_to_status_id_str": "1",
    "quoted_tweet": {"id_str": "99", "user": {"screen_name": "quoted_guy"}},
}


def test_snowflake_date():
    dt = el.snowflake_to_datetime("1928421128401846272")
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat().startswith("2025-05-30")
    assert el.snowflake_to_datetime("20") is None       # pre-snowflake id
    assert el.snowflake_to_datetime("nope") is None


@pytest.mark.parametrize("tweet_id,expected", [
    # expected values produced by node: ((Number(id)/1e15)*Math.PI).toString(36).replace(/(0+|\.)/g,'')
    ("1928421128401846272", "4oabahnkzf7"),
    ("1932407394923446272", "4omu4l9pdpo"),
    ("1769332855403446272", "4aeitxrm8cv"),
    ("20", "6dq1a2xwd93"),
    ("1000000000000000000", "2f9lc2ug9mm"),
])
def test_syndication_token_matches_js(tweet_id, expected):
    assert el.syndication_token(tweet_id) == expected


def test_parse_video_tweet():
    d = el.parse_syndication(FIXTURE_VIDEO)
    assert d["status"] == "ok"
    assert d["author_username"] == "example_rockets"
    assert d["author_verified"] == 1
    assert d["media_type"] == "mixed"
    assert d["has_video"] == 1 and d["has_photo"] == 1 and d["has_gif"] == 0
    assert d["video_duration_ms"] == 32000
    assert d["is_reply"] == 1 and d["in_reply_to_username"] == "someone"
    assert d["is_quote"] == 1 and d["quoted_author_username"] == "quoted_guy"
    assert json.loads(d["url_domains"]) == ["rockets.example.com"]
    assert json.loads(d["hashtags"]) == ["SpaceX"]
    assert d["favorite_count"] == 1234 and d["reply_count"] == 56


def test_parse_text_only_and_tombstone():
    d = el.parse_syndication({"__typename": "Tweet", "id_str": "1", "text": "hi", "user": {"screen_name": "a"}})
    assert d["media_type"] == "none" and d["has_video"] == 0 and d["video_duration_ms"] is None
    t = el.parse_syndication({"__typename": "TweetTombstone", "tombstone": {}})
    assert t["status"] == "unavailable"


def test_store_and_resume(tmp_path):
    conn = el.connect(tmp_path / "t.db")
    for tid in ("1928058740536246272", "1928421128401846272", "1769332855403446272"):
        conn.execute("INSERT INTO likes (tweet_id, full_text) VALUES (?, 'x')", (tid,))
    assert el.backfill_snowflake_dates(conn) == 3
    assert len(el.pending_ids(conn, retry_errors=False, limit=None)) == 3

    assert el.store_result(conn, "1928058740536246272", "ok", FIXTURE_VIDEO) == "ok"
    assert el.store_result(conn, "1928421128401846272", "unavailable", "http 404") == "unavailable"
    assert el.store_result(conn, "1769332855403446272", "error", "boom") == "error"

    assert el.pending_ids(conn, retry_errors=False, limit=None) == []
    assert el.pending_ids(conn, retry_errors=True, limit=None) == ["1769332855403446272"]

    row = conn.execute("SELECT * FROM like_details WHERE tweet_id='1928058740536246272'").fetchone()
    assert row["has_video"] == 1 and row["snowflake_created_at"].startswith("2025-05-29")
    # unavailable rows keep the derived date so time-based analysis still covers them
    row = conn.execute("SELECT * FROM like_details WHERE tweet_id='1928421128401846272'").fetchone()
    assert row["snowflake_created_at"] and row["author_username"] is None


def test_tag_text():
    tags = el.tag_text("Starship stacked for the next Falcon flight — pure rocket science 🚀")
    assert "space" in tags
    assert tags["space"] > 0
    assert el.tag_text("nothing to see here") == {}
    assert "ai-ml" in el.tag_text("Claude and GPT agents doing inference on GPUs")


def test_tag_topics_uses_details_text(tmp_path):
    conn = el.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO likes (tweet_id, full_text) VALUES ('1928058740536246272', 'truncated…')")
    el.store_result(conn, "1928058740536246272", "ok", FIXTURE_VIDEO)
    counts = el.tag_topics(conn)
    assert counts["_tweets"] == 1
    topics = {r[0] for r in conn.execute("SELECT topic FROM like_topics")}
    assert "space" in topics


def test_load_archives(tmp_path):
    arch = tmp_path / "twitter-archive-2025-01-01" / "data"
    arch.mkdir(parents=True)
    (arch / "like.js").write_text(
        'window.YTD.like.part0 = [\n  {"like": {"tweetId": "1928058740536246272", "fullText": "a", '
        '"expandedUrl": "https://twitter.com/i/web/status/1928058740536246272"}},\n'
        '  {"like": {"tweetId": "1928421128401846272", "fullText": "b"}}\n]'
    )
    conn = el.connect(tmp_path / "t.db")
    s = el.load_archives(conn, root=tmp_path)
    assert s["_total_new"] == 2
    s2 = el.load_archives(conn, root=tmp_path)   # idempotent
    assert s2["_total_new"] == 0
    assert conn.execute("SELECT COUNT(*) FROM likes").fetchone()[0] == 2
