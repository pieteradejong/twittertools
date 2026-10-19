"""
Likes Review API — filter, summarize and export liked tweets enriched by
scripts/enrich_likes.py (tables: likes, like_details, like_topics).

Mounted in src/main.py via `app.include_router(likes_review.router)`.
All queries are plain SQL against data/x_data.db; nothing here touches the
network, so the endpoints work offline once enrichment has run.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "x_data.db"

router = APIRouter(prefix="/api/likes-review", tags=["likes-review"])

MEDIA_FILTERS = {"any", "none", "photo", "video", "gif", "mixed", "any-media"}
SORTS = {
    "newest": "COALESCE(d.created_at, d.snowflake_created_at) DESC",
    "oldest": "COALESCE(d.created_at, d.snowflake_created_at) ASC",
    "popular": "d.favorite_count DESC NULLS LAST",
    "longest-video": "d.video_duration_ms DESC NULLS LAST",
}


def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(500, f"database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "like_details" not in have:
        raise HTTPException(
            503, "like_details table missing — run `python scripts/enrich_likes.py --load-archives` first"
        )
    return conn


def _loads(s: Optional[str]) -> List[Any]:
    try:
        return json.loads(s) if s else []
    except ValueError:
        return []


class Filters:
    """Translate query params into a WHERE clause + params. Kept as a small
    object so /items, /export and /summary share exactly the same semantics."""

    def __init__(
        self,
        q: Optional[str] = None,
        author: Optional[str] = None,
        media: str = "any",
        topic: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[str] = None,  # YYYY-MM
        lang: Optional[str] = None,
        domain: Optional[str] = None,
        is_reply: Optional[bool] = None,
        is_quote: Optional[bool] = None,
        status: Optional[str] = None,
        min_video_seconds: Optional[int] = None,
    ):
        if media not in MEDIA_FILTERS:
            raise HTTPException(400, f"media must be one of {sorted(MEDIA_FILTERS)}")
        self.where: List[str] = []
        self.params: List[Any] = []
        self.joins: List[str] = []

        if q:
            self.where.append("(COALESCE(d.text, l.full_text) LIKE ? OR d.author_username LIKE ? OR d.author_name LIKE ?)")
            like = f"%{q}%"
            self.params += [like, like, like]
        if author:
            self.where.append("LOWER(d.author_username) = LOWER(?)")
            self.params.append(author.lstrip("@"))
        if media == "any-media":
            self.where.append("d.media_type IS NOT NULL AND d.media_type != 'none'")
        elif media != "any":
            self.where.append("d.media_type = ?")
            self.params.append(media)
        if topic:
            self.joins.append("JOIN like_topics t ON t.tweet_id = l.tweet_id AND t.topic = ?")
            self.params.insert(0, topic)  # join params come before WHERE params
        if year:
            self.where.append("substr(COALESCE(d.created_at, d.snowflake_created_at), 1, 4) = ?")
            self.params.append(str(year))
        if month:
            self.where.append("substr(COALESCE(d.created_at, d.snowflake_created_at), 1, 7) = ?")
            self.params.append(month)
        if lang:
            self.where.append("d.lang = ?")
            self.params.append(lang)
        if domain:
            self.where.append("d.url_domains LIKE ?")
            self.params.append(f'%"{domain}"%')
        if is_reply is not None:
            self.where.append("COALESCE(d.is_reply, 0) = ?")
            self.params.append(int(is_reply))
        if is_quote is not None:
            self.where.append("COALESCE(d.is_quote, 0) = ?")
            self.params.append(int(is_quote))
        if status:
            self.where.append("d.status = ?")
            self.params.append(status)
        if min_video_seconds:
            self.where.append("d.video_duration_ms >= ?")
            self.params.append(min_video_seconds * 1000)

    @property
    def sql_from(self) -> str:
        return "FROM likes l LEFT JOIN like_details d ON d.tweet_id = l.tweet_id " + " ".join(self.joins)

    @property
    def sql_where(self) -> str:
        return ("WHERE " + " AND ".join(self.where)) if self.where else ""


def _row_to_item(r: sqlite3.Row, topics: Dict[str, List[str]]) -> Dict[str, Any]:
    created = r["created_at"] or r["snowflake_created_at"]
    username = r["author_username"]
    return {
        "id": r["tweet_id"],
        "text": r["text"] or r["full_text"] or "",
        "created_at": created,
        "status": r["status"] or "pending",
        "tweet_url": f"https://x.com/{username}/status/{r['tweet_id']}" if username else f"https://x.com/i/web/status/{r['tweet_id']}",
        "author": {
            "id": r["author_id"],
            "username": username,
            "display_name": r["author_name"],
            "avatar_url": r["author_avatar_url"],
            "verified": bool(r["author_verified"]),
        },
        "metrics": {"like_count": r["favorite_count"] or 0, "reply_count": r["reply_count"] or 0, "retweet_count": 0},
        "lang": r["lang"],
        "media_type": r["media_type"] or ("unknown" if (r["status"] or "pending") != "ok" else "none"),
        "has_video": bool(r["has_video"]),
        "has_photo": bool(r["has_photo"]),
        "has_gif": bool(r["has_gif"]),
        "video_duration_ms": r["video_duration_ms"],
        "media_urls": _loads(r["media_urls"]),
        "urls": _loads(r["urls"]),
        "url_domains": _loads(r["url_domains"]),
        "hashtags": _loads(r["hashtags"]),
        "is_reply": bool(r["is_reply"]),
        "in_reply_to_username": r["in_reply_to_username"],
        "is_quote": bool(r["is_quote"]),
        "quoted_author_username": r["quoted_author_username"],
        "topics": topics.get(r["tweet_id"], []),
    }


def _topics_for(conn: sqlite3.Connection, ids: List[str]) -> Dict[str, List[str]]:
    if not ids:
        return {}
    out: Dict[str, List[str]] = {}
    for chunk in (ids[i : i + 500] for i in range(0, len(ids), 500)):
        rows = conn.execute(
            f"SELECT tweet_id, topic FROM like_topics WHERE tweet_id IN ({','.join('?' * len(chunk))}) "
            "ORDER BY score DESC",
            chunk,
        )
        for tid, topic in rows:
            out.setdefault(tid, []).append(topic)
    return out


def _select_items(conn: sqlite3.Connection, f: Filters, sort: str, limit: Optional[int], offset: int):
    order = SORTS.get(sort)
    if not order:
        raise HTTPException(400, f"sort must be one of {sorted(SORTS)}")
    sql = f"SELECT l.tweet_id, l.full_text, d.* {f.sql_from} {f.sql_where} ORDER BY {order}"
    params = list(f.params)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    topics = _topics_for(conn, [r["tweet_id"] for r in rows])
    return [_row_to_item(r, topics) for r in rows]


@router.get("/items")
def list_items(
    q: Optional[str] = None,
    author: Optional[str] = None,
    media: str = "any",
    topic: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    lang: Optional[str] = None,
    domain: Optional[str] = None,
    is_reply: Optional[bool] = None,
    is_quote: Optional[bool] = None,
    status: Optional[str] = None,
    min_video_seconds: Optional[int] = None,
    sort: str = Query("newest", description="newest | oldest | popular | longest-video"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated, filtered likes. Every filter is optional and they AND together."""
    f = Filters(q, author, media, topic, year, month, lang, domain, is_reply, is_quote, status, min_video_seconds)
    conn = _conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) {f.sql_from} {f.sql_where}", f.params).fetchone()[0]
        items = _select_items(conn, f, sort, limit, offset)
        return {"total": total, "limit": limit, "offset": offset, "items": items}
    finally:
        conn.close()


@router.get("/summary")
def summary(
    q: Optional[str] = None,
    author: Optional[str] = None,
    media: str = "any",
    topic: Optional[str] = None,
    year: Optional[int] = None,
    lang: Optional[str] = None,
    domain: Optional[str] = None,
):
    """Aggregates for the current filter set (so charts follow the filters)."""
    f = Filters(q=q, author=author, media=media, topic=topic, year=year, lang=lang, domain=domain)
    conn = _conn()

    def group(expr: str, limit: int = 20, extra_where: str = "") -> List[Dict[str, Any]]:
        where = f.sql_where
        if extra_where:
            where = (where + " AND " if where else "WHERE ") + extra_where
        rows = conn.execute(
            f"SELECT {expr} AS k, COUNT(*) AS c {f.sql_from} {where} GROUP BY k ORDER BY c DESC LIMIT {limit}",
            f.params,
        ).fetchall()
        return [{"key": r["k"], "count": r["c"]} for r in rows if r["k"] is not None]

    try:
        total = conn.execute(f"SELECT COUNT(*) {f.sql_from} {f.sql_where}", f.params).fetchone()[0]
        by_month = sorted(
            group("substr(COALESCE(d.created_at, d.snowflake_created_at), 1, 7)", limit=400), key=lambda x: x["key"]
        )
        video_seconds = conn.execute(
            f"SELECT COALESCE(SUM(d.video_duration_ms), 0) / 1000 {f.sql_from} {f.sql_where}", f.params
        ).fetchone()[0]
        # topics need their own join, so query directly
        tw = f.sql_where
        topics = conn.execute(
            f"SELECT lt.topic AS k, COUNT(DISTINCT lt.tweet_id) AS c {f.sql_from} "
            f"JOIN like_topics lt ON lt.tweet_id = l.tweet_id {tw} GROUP BY k ORDER BY c DESC",
            f.params,
        ).fetchall()
        # domains are stored as JSON arrays; explode with json_each
        domains = conn.execute(
            f"SELECT je.value AS k, COUNT(*) AS c {f.sql_from}, json_each(COALESCE(d.url_domains, '[]')) je "
            f"{tw} GROUP BY k ORDER BY c DESC LIMIT 25",
            f.params,
        ).fetchall()
        return {
            "total": total,
            "status": group("d.status"),
            "media_type": group("d.media_type"),
            "video_total_seconds": video_seconds,
            "by_year": sorted(group("substr(COALESCE(d.created_at, d.snowflake_created_at), 1, 4)", limit=30), key=lambda x: x["key"]),
            "by_month": by_month,
            "top_authors": group("d.author_username", limit=30, extra_where="d.author_username IS NOT NULL"),
            "languages": group("d.lang", limit=15),
            "topics": [{"key": r["k"], "count": r["c"]} for r in topics],
            "top_domains": [{"key": r["k"], "count": r["c"]} for r in domains],
            "reply_share": group("COALESCE(d.is_reply, 0)"),
            "quote_share": group("COALESCE(d.is_quote, 0)"),
        }
    finally:
        conn.close()


@router.get("/topics")
def topics():
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT topic, method, COUNT(*) c FROM like_topics GROUP BY topic, method ORDER BY c DESC"
        ).fetchall()
        return [{"topic": r["topic"], "method": r["method"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


@router.post("/tag-topics")
def tag_topics():
    """Re-run the keyword tagger from scripts/enrich_likes.py (fast, offline)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import enrich_likes  # noqa: WPS433

    conn = enrich_likes.connect(DB_PATH)
    try:
        counts = enrich_likes.tag_topics(conn)
    finally:
        conn.close()
    return counts


@router.get("/export")
def export(
    format: str = Query("csv", description="csv | json | md"),
    q: Optional[str] = None,
    author: Optional[str] = None,
    media: str = "any",
    topic: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[str] = None,
    lang: Optional[str] = None,
    domain: Optional[str] = None,
    is_reply: Optional[bool] = None,
    is_quote: Optional[bool] = None,
    sort: str = "newest",
):
    """Export the filtered set. CSV for spreadsheets, JSON for scripts, Markdown for notes."""
    f = Filters(q, author, media, topic, year, month, lang, domain, is_reply, is_quote)
    conn = _conn()
    try:
        items = _select_items(conn, f, sort, None, 0)
    finally:
        conn.close()

    if format == "json":
        return StreamingResponse(
            io.BytesIO(json.dumps(items, indent=2, ensure_ascii=False).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=likes.json"},
        )
    if format == "md":
        lines = [f"# Liked tweets ({len(items)})", ""]
        for it in items:
            a = it["author"]
            who = f"@{a['username']}" if a["username"] else "unknown"
            badges = " ".join(
                b for b in [
                    "🎬" if it["has_video"] else "",
                    "🖼️" if it["has_photo"] else "",
                    f"[{', '.join(it['topics'])}]" if it["topics"] else "",
                ] if b
            )
            date = (it["created_at"] or "")[:10]
            text = it["text"].replace("\n", "\n> ")
            lines += [f"## {who} · {date} {badges}".rstrip(), "", f"> {text}", "", f"{it['tweet_url']}", ""]
        return PlainTextResponse("\n".join(lines), media_type="text/markdown",
                                 headers={"Content-Disposition": "attachment; filename=likes.md"})

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["tweet_id", "url", "created_at", "author_username", "author_name", "text", "lang", "media_type",
                "has_video", "video_duration_s", "photo_count", "is_reply", "is_quote", "quoted_author",
                "favorite_count", "reply_count", "topics", "url_domains", "status"])
    for it in items:
        w.writerow([
            it["id"], it["tweet_url"], it["created_at"], it["author"]["username"], it["author"]["display_name"],
            it["text"], it["lang"], it["media_type"], int(it["has_video"]),
            round((it["video_duration_ms"] or 0) / 1000, 1) if it["video_duration_ms"] else "",
            len([u for u in it["media_urls"]]) if it["has_photo"] else 0,
            int(it["is_reply"]), int(it["is_quote"]), it["quoted_author_username"],
            it["metrics"]["like_count"], it["metrics"]["reply_count"],
            "|".join(it["topics"]), "|".join(it["url_domains"]), it["status"],
        ])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=likes.csv"})
