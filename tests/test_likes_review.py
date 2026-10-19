"""API tests for src/likes_review.py using a seeded temp DB (no network)."""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import enrich_likes as el  # noqa: E402
from src import likes_review  # noqa: E402
from tests.test_enrich_likes import FIXTURE_VIDEO  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "x.db"
    conn = el.connect(db)
    conn.execute("INSERT INTO likes (tweet_id, full_text) VALUES ('1928058740536246272', 'video one')")
    conn.execute("INSERT INTO likes (tweet_id, full_text) VALUES ('1928421128401846272', 'plain text about Python')")
    conn.execute("INSERT INTO likes (tweet_id, full_text) VALUES ('1769332855403446272', 'gone')")
    el.backfill_snowflake_dates(conn)
    el.store_result(conn, "1928058740536246272", "ok", FIXTURE_VIDEO)
    el.store_result(conn, "1928421128401846272", "ok", {"__typename": "Tweet", "id_str": "1928421128401846272",
                    "text": "plain text about Python", "lang": "en", "created_at": "2025-05-30T10:00:00.000Z",
                    "user": {"screen_name": "coder", "name": "Coder"}, "favorite_count": 5})
    el.store_result(conn, "1769332855403446272", "unavailable", "http 404")
    el.tag_topics(conn)
    conn.close()
    monkeypatch.setattr(likes_review, "DB_PATH", db)
    app = FastAPI()
    app.include_router(likes_review.router)
    return TestClient(app)


def test_items_default(client):
    r = client.get("/api/likes-review/items")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    ids = [i["id"] for i in body["items"]]
    assert ids[0] == "1928421128401846272"          # newest by created_at
    assert ids[-1] == "1769332855403446272"          # unavailable still listed, dated via snowflake
    video = next(i for i in body["items"] if i["id"] == "1928058740536246272")
    assert video["has_video"] and video["video_duration_ms"] == 32000 and "space" in video["topics"]
    assert video["tweet_url"] == "https://x.com/example_rockets/status/1928058740536246272"


def test_filters(client):
    assert client.get("/api/likes-review/items?media=video").json()["total"] == 0   # it's 'mixed'
    assert client.get("/api/likes-review/items?media=mixed").json()["total"] == 1
    assert client.get("/api/likes-review/items?media=any-media").json()["total"] == 1
    assert client.get("/api/likes-review/items?media=none").json()["total"] == 1
    assert client.get("/api/likes-review/items?author=@example_rockets").json()["total"] == 1
    assert client.get("/api/likes-review/items?topic=programming").json()["total"] == 1
    assert client.get("/api/likes-review/items?q=python").json()["total"] == 1
    assert client.get("/api/likes-review/items?status=unavailable").json()["total"] == 1
    assert client.get("/api/likes-review/items?year=2024").json()["total"] == 1
    assert client.get("/api/likes-review/items?domain=rockets.example.com").json()["total"] == 1
    assert client.get("/api/likes-review/items?is_reply=true").json()["total"] == 1
    assert client.get("/api/likes-review/items?min_video_seconds=10").json()["total"] == 1
    assert client.get("/api/likes-review/items?min_video_seconds=60").json()["total"] == 0
    assert client.get("/api/likes-review/items?media=bogus").status_code == 400
    assert client.get("/api/likes-review/items?sort=bogus").status_code == 400
    assert client.get("/api/likes-review/items?topic=space&media=mixed").json()["total"] == 1


def test_summary(client):
    s = client.get("/api/likes-review/summary").json()
    assert s["total"] == 3
    assert {x["key"]: x["count"] for x in s["media_type"]} == {"mixed": 1, "none": 1}
    assert s["video_total_seconds"] == 32
    assert any(t["key"] == "space" for t in s["topics"])
    assert s["top_domains"][0]["key"] == "rockets.example.com"
    years = {x["key"] for x in s["by_year"]}
    assert years == {"2024", "2025"}
    s2 = client.get("/api/likes-review/summary?author=example_rockets").json()
    assert s2["total"] == 1
    s3 = client.get("/api/likes-review/summary?topic=space&media=mixed").json()
    assert s3["total"] == 1 and s3["top_domains"][0]["key"] == "rockets.example.com"
    assert any(t["key"] == "space" for t in s3["topics"])


def test_export_formats(client):
    csv_ = client.get("/api/likes-review/export?format=csv")
    assert csv_.status_code == 200 and csv_.text.startswith("tweet_id,url")
    assert csv_.text.count("\n") >= 4
    md = client.get("/api/likes-review/export?format=md&media=mixed")
    assert "@example_rockets" in md.text and "🎬" in md.text
    js = client.get("/api/likes-review/export?format=json&topic=space").json()
    assert len(js) == 1


def test_tag_topics_endpoint(client):
    r = client.post("/api/likes-review/tag-topics")
    assert r.status_code == 200 and r.json()["_tweets"] == 3
