#!/usr/bin/env python3
"""
Enrich liked tweets with metadata the X archive does not include.

The archive's like.js only carries (tweetId, fullText, expandedUrl). This script:

  1. Unions likes from every archive folder in the repo into the `likes` table
     (INSERT OR IGNORE — nothing already there is modified).
  2. Derives each tweet's creation time from its Snowflake ID (offline, exact to
     the millisecond — no network needed).
  3. Fetches author / media / video / metrics per tweet from X's public
     syndication endpoint (the one embedded tweets and react-tweet use) and
     stores the result in `like_details`. Resumable: re-running only fetches
     rows that are missing or previously errored.
  4. Tags likes with topics via keyword rules into `like_topics` (fast,
     deterministic, transparent). The existing semantic classifier can still be
     run on top for fuzzier matching.

Usage:
    python scripts/enrich_likes.py --load-archives      # step 1 + 2
    python scripts/enrich_likes.py --fetch              # step 3 (needs network, ~1 req/s)
    python scripts/enrich_likes.py --fetch --limit 50   # try a small batch first
    python scripts/enrich_likes.py --tag-topics         # step 4
    python scripts/enrich_likes.py --stats
    python scripts/enrich_likes.py --all                # everything, in order

Notes:
  * The syndication endpoint is unofficial. Be polite: default delay is 1s with
    jitter, and 429/5xx responses trigger exponential backoff. Ctrl-C is safe;
    progress is committed per row.
  * Deleted / protected / suspended tweets come back as 404 or a tombstone and
    are recorded with status='unavailable' so they are not retried forever.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "x_data.db"
SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result"
TWITTER_EPOCH_MS = 1288834974657  # 2010-11-04T01:42:54.657Z
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

log = logging.getLogger("enrich_likes")


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS likes (
    tweet_id TEXT PRIMARY KEY,
    full_text TEXT,
    expanded_url TEXT,
    liked_at TEXT,
    author_id TEXT,
    author_username TEXT
);

CREATE TABLE IF NOT EXISTS like_details (
    tweet_id            TEXT PRIMARY KEY REFERENCES likes(tweet_id),
    status              TEXT NOT NULL,          -- ok | unavailable | error
    error               TEXT,
    fetched_at          TEXT NOT NULL,
    -- timing
    snowflake_created_at TEXT,                  -- derived from the ID, always present
    created_at          TEXT,                   -- from the API when status = ok
    -- author
    author_id           TEXT,
    author_username     TEXT,
    author_name         TEXT,
    author_avatar_url   TEXT,
    author_verified     INTEGER,
    -- content
    text                TEXT,
    lang                TEXT,
    is_reply            INTEGER,
    in_reply_to_username TEXT,
    is_quote            INTEGER,
    quoted_tweet_id     TEXT,
    quoted_author_username TEXT,
    has_card            INTEGER,                -- link preview / poll card
    possibly_sensitive  INTEGER,
    -- media
    media_type          TEXT,                   -- none | photo | video | gif | mixed
    has_video           INTEGER NOT NULL DEFAULT 0,
    has_photo           INTEGER NOT NULL DEFAULT 0,
    has_gif             INTEGER NOT NULL DEFAULT 0,
    photo_count         INTEGER NOT NULL DEFAULT 0,
    video_count         INTEGER NOT NULL DEFAULT 0,
    video_duration_ms   INTEGER,                -- sum over videos
    media_urls          TEXT,                   -- JSON list of media_url_https / poster urls
    -- links
    urls                TEXT,                   -- JSON list of expanded URLs
    url_domains         TEXT,                   -- JSON list of domains (deduped)
    hashtags            TEXT,                   -- JSON list
    mentions            TEXT,                   -- JSON list of screen names
    -- metrics
    favorite_count      INTEGER,
    reply_count         INTEGER,
    raw_json            TEXT
);
CREATE INDEX IF NOT EXISTS idx_like_details_status ON like_details(status);
CREATE INDEX IF NOT EXISTS idx_like_details_author ON like_details(author_username);
CREATE INDEX IF NOT EXISTS idx_like_details_media  ON like_details(media_type);
CREATE INDEX IF NOT EXISTS idx_like_details_created ON like_details(snowflake_created_at);

CREATE TABLE IF NOT EXISTS like_topics (
    tweet_id TEXT NOT NULL REFERENCES likes(tweet_id),
    topic    TEXT NOT NULL,
    score    REAL NOT NULL,
    method   TEXT NOT NULL,                     -- keyword | semantic
    PRIMARY KEY (tweet_id, topic, method)
);
CREATE INDEX IF NOT EXISTS idx_like_topics_topic ON like_topics(topic);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# Step 1: archives -> likes
# --------------------------------------------------------------------------- #
def load_ytd_js(path: Path) -> List[Dict[str, Any]]:
    """Parse a `window.YTD.<name>.part0 = [...]` file into Python objects."""
    text = path.read_text(encoding="utf-8")
    start = text.index("[")
    return json.loads(text[start:])


def find_like_files(root: Path = REPO_ROOT) -> List[Path]:
    """All like.js (and like-part*.js) files under any archive folder in the repo."""
    files = sorted(root.glob("**/twitter-*/data/like*.js"))
    return [f for f in files if f.is_file()]


def load_archives(conn: sqlite3.Connection, root: Path = REPO_ROOT) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    total_new = 0
    for f in find_like_files(root):
        entries = load_ytd_js(f)
        before = conn.total_changes
        for entry in entries:
            like = entry.get("like") or entry
            tid = like.get("tweetId")
            if not tid:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO likes (tweet_id, full_text, expanded_url) VALUES (?, ?, ?)",
                (tid, like.get("fullText"), like.get("expandedUrl")),
            )
        added = conn.total_changes - before
        summary[str(f.relative_to(root))] = added
        total_new += added
        log.info("%s: %d entries, %d new", f.relative_to(root), len(entries), added)
    conn.commit()
    summary["_total_new"] = total_new
    return summary


# --------------------------------------------------------------------------- #
# Step 2: Snowflake timestamps
# --------------------------------------------------------------------------- #
def snowflake_to_datetime(tweet_id: str) -> Optional[datetime]:
    """Twitter IDs since late 2010 encode a ms timestamp in the top 41 bits."""
    try:
        n = int(tweet_id)
    except (TypeError, ValueError):
        return None
    if n < (1 << 22):  # pre-Snowflake sequential IDs carry no timestamp
        return None
    ms = (n >> 22) + TWITTER_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def backfill_snowflake_dates(conn: sqlite3.Connection) -> int:
    """Ensure every like has a like_details row with at least the derived date."""
    rows = conn.execute(
        """SELECT l.tweet_id FROM likes l
           LEFT JOIN like_details d ON d.tweet_id = l.tweet_id
           WHERE d.tweet_id IS NULL OR d.snowflake_created_at IS NULL"""
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    for (tid,) in rows:
        dt = snowflake_to_datetime(tid)
        conn.execute(
            """INSERT INTO like_details (tweet_id, status, fetched_at, snowflake_created_at)
               VALUES (?, 'pending', ?, ?)
               ON CONFLICT(tweet_id) DO UPDATE SET snowflake_created_at = excluded.snowflake_created_at""",
            (tid, now, dt.isoformat() if dt else None),
        )
    conn.commit()
    return len(rows)


# --------------------------------------------------------------------------- #
# Step 3: syndication fetch
# --------------------------------------------------------------------------- #
def _double_to_radix36(value: float) -> str:
    """Port of V8's DoubleToRadixCString for radix 36 (what Number#toString(36) does).

    Python has no built-in float->base36, and the token must match what JS
    produces, so we reproduce the digit-generation loop faithfully.
    """
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    radix = 36
    if value == 0:
        return "0"
    negative = value < 0
    value = abs(value)
    integer = math.floor(value)
    fraction = value - integer
    delta = 0.5 * (math.nextafter(value, math.inf) - value)
    delta = max(math.nextafter(0.0, 1.0), delta)

    frac_digits: List[int] = []
    if fraction >= delta:
        while True:
            fraction *= radix
            delta *= radix
            digit = int(fraction)
            frac_digits.append(digit)
            fraction -= digit
            if fraction > 0.5 or (fraction == 0.5 and (digit & 1)):
                if fraction + delta > 1:
                    # round up, propagating carries leftwards
                    while True:
                        if not frac_digits:
                            integer += 1
                            break
                        d = frac_digits.pop()
                        if d + 1 < radix:
                            frac_digits.append(d + 1)
                            break
                    break
            if fraction < delta:
                break

    int_digits = ""
    n = int(integer)
    while n > 0:
        int_digits = chars[n % radix] + int_digits
        n //= radix
    int_digits = int_digits or "0"
    out = int_digits
    if frac_digits:
        out += "." + "".join(chars[d] for d in frac_digits)
    return ("-" if negative else "") + out


def syndication_token(tweet_id: str) -> str:
    """JS: ((Number(id) / 1e15) * Math.PI).toString(36).replace(/(0+|\\.)/g, '')"""
    value = (float(int(tweet_id)) / 1e15) * math.pi
    return re.sub(r"(0+|\.)", "", _double_to_radix36(value))


def _domain(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    host = (m.group(1) if m else "").lower()
    return host[4:] if host.startswith("www.") else host


def parse_syndication(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a syndication tweet JSON into like_details columns."""
    if not data or data.get("__typename") == "TweetTombstone":
        return {"status": "unavailable", "error": "tombstone"}

    user = data.get("user") or {}
    entities = data.get("entities") or {}
    media = data.get("mediaDetails") or []

    photo_count = sum(1 for m in media if m.get("type") == "photo")
    video_count = sum(1 for m in media if m.get("type") == "video")
    gif_count = sum(1 for m in media if m.get("type") == "animated_gif")
    duration = sum(
        int((m.get("video_info") or {}).get("duration_millis") or 0)
        for m in media
        if m.get("type") == "video"
    )
    kinds = {k for k, c in (("photo", photo_count), ("video", video_count), ("gif", gif_count)) if c}
    if not kinds:
        media_type = "none"
    elif len(kinds) == 1:
        media_type = kinds.pop()
    else:
        media_type = "mixed"

    urls = [u.get("expanded_url") or u.get("url") for u in entities.get("urls") or []]
    urls = [u for u in urls if u]
    domains = sorted({_domain(u) for u in urls if _domain(u)})
    quoted = data.get("quoted_tweet") or {}
    parent = data.get("parent") or {}

    return {
        "status": "ok",
        "error": None,
        "created_at": data.get("created_at"),
        "author_id": user.get("id_str"),
        "author_username": user.get("screen_name"),
        "author_name": user.get("name"),
        "author_avatar_url": user.get("profile_image_url_https"),
        "author_verified": int(bool(user.get("verified") or user.get("is_blue_verified"))),
        "text": data.get("text"),
        "lang": data.get("lang"),
        "is_reply": int(bool(data.get("in_reply_to_status_id_str") or parent)),
        "in_reply_to_username": data.get("in_reply_to_screen_name")
        or (parent.get("user") or {}).get("screen_name"),
        "is_quote": int(bool(quoted)),
        "quoted_tweet_id": quoted.get("id_str"),
        "quoted_author_username": (quoted.get("user") or {}).get("screen_name"),
        "has_card": int(bool(data.get("card"))),
        "possibly_sensitive": int(bool(data.get("possibly_sensitive"))),
        "media_type": media_type,
        "has_video": int(video_count > 0),
        "has_photo": int(photo_count > 0),
        "has_gif": int(gif_count > 0),
        "photo_count": photo_count,
        "video_count": video_count + gif_count,
        "video_duration_ms": duration or None,
        "media_urls": json.dumps([m.get("media_url_https") for m in media if m.get("media_url_https")]),
        "urls": json.dumps(urls),
        "url_domains": json.dumps(domains),
        "hashtags": json.dumps([h.get("text") for h in entities.get("hashtags") or [] if h.get("text")]),
        "mentions": json.dumps(
            [m.get("screen_name") for m in entities.get("user_mentions") or [] if m.get("screen_name")]
        ),
        "favorite_count": data.get("favorite_count"),
        "reply_count": data.get("conversation_count"),
        "raw_json": json.dumps(data, separators=(",", ":")),
    }


class SyndicationClient:
    """Small polite HTTP client. Returns (status, payload) where status is
    'ok' | 'unavailable' | 'error' and payload is parsed JSON or an error string."""

    def __init__(self, delay: float = 1.0, timeout: float = 20.0, max_retries: int = 5):
        import requests  # local import so --load-archives works without it

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch(self, tweet_id: str) -> Tuple[str, Any]:
        import requests

        params = {"id": tweet_id, "token": syndication_token(tweet_id), "lang": "en"}
        backoff = 5.0
        for attempt in range(1, self.max_retries + 1):
            try:
                r = self.session.get(SYNDICATION_URL, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                log.warning("%s: network error (%s), retry %d/%d", tweet_id, e, attempt, self.max_retries)
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue

            if r.status_code == 200:
                if not r.content or not r.text.strip():
                    return "unavailable", "empty body"
                try:
                    return "ok", r.json()
                except ValueError:
                    return "error", f"bad json: {r.text[:200]!r}"
            if r.status_code in (404, 403, 401):
                return "unavailable", f"http {r.status_code}"
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                log.warning("%s: http %d, sleeping %.0fs (retry %d/%d)", tweet_id, r.status_code, wait, attempt, self.max_retries)
                time.sleep(wait)
                backoff = min(backoff * 2, 300)
                continue
            return "error", f"http {r.status_code}: {r.text[:200]!r}"
        return "error", "max retries exceeded"

    def sleep(self) -> None:
        time.sleep(self.delay + random.uniform(0, self.delay * 0.5))


UPSERT_DETAILS = """
INSERT INTO like_details (
    tweet_id, status, error, fetched_at, snowflake_created_at, created_at,
    author_id, author_username, author_name, author_avatar_url, author_verified,
    text, lang, is_reply, in_reply_to_username, is_quote, quoted_tweet_id, quoted_author_username,
    has_card, possibly_sensitive, media_type, has_video, has_photo, has_gif, photo_count, video_count,
    video_duration_ms, media_urls, urls, url_domains, hashtags, mentions, favorite_count, reply_count, raw_json
) VALUES (
    :tweet_id, :status, :error, :fetched_at, :snowflake_created_at, :created_at,
    :author_id, :author_username, :author_name, :author_avatar_url, :author_verified,
    :text, :lang, :is_reply, :in_reply_to_username, :is_quote, :quoted_tweet_id, :quoted_author_username,
    :has_card, :possibly_sensitive, :media_type, :has_video, :has_photo, :has_gif, :photo_count, :video_count,
    :video_duration_ms, :media_urls, :urls, :url_domains, :hashtags, :mentions, :favorite_count, :reply_count, :raw_json
)
ON CONFLICT(tweet_id) DO UPDATE SET
    status=excluded.status, error=excluded.error, fetched_at=excluded.fetched_at,
    snowflake_created_at=COALESCE(excluded.snowflake_created_at, like_details.snowflake_created_at),
    created_at=excluded.created_at,
    author_id=excluded.author_id, author_username=excluded.author_username, author_name=excluded.author_name,
    author_avatar_url=excluded.author_avatar_url, author_verified=excluded.author_verified,
    text=excluded.text, lang=excluded.lang, is_reply=excluded.is_reply, in_reply_to_username=excluded.in_reply_to_username,
    is_quote=excluded.is_quote, quoted_tweet_id=excluded.quoted_tweet_id, quoted_author_username=excluded.quoted_author_username,
    has_card=excluded.has_card, possibly_sensitive=excluded.possibly_sensitive, media_type=excluded.media_type,
    has_video=excluded.has_video, has_photo=excluded.has_photo, has_gif=excluded.has_gif,
    photo_count=excluded.photo_count, video_count=excluded.video_count, video_duration_ms=excluded.video_duration_ms,
    media_urls=excluded.media_urls, urls=excluded.urls, url_domains=excluded.url_domains, hashtags=excluded.hashtags,
    mentions=excluded.mentions, favorite_count=excluded.favorite_count, reply_count=excluded.reply_count,
    raw_json=excluded.raw_json
"""

DETAIL_COLUMNS = [
    "created_at", "author_id", "author_username", "author_name", "author_avatar_url", "author_verified",
    "text", "lang", "is_reply", "in_reply_to_username", "is_quote", "quoted_tweet_id", "quoted_author_username",
    "has_card", "possibly_sensitive", "media_type", "has_video", "has_photo", "has_gif", "photo_count",
    "video_count", "video_duration_ms", "media_urls", "urls", "url_domains", "hashtags", "mentions",
    "favorite_count", "reply_count", "raw_json",
]


def _blank_details() -> Dict[str, Any]:
    d: Dict[str, Any] = {c: None for c in DETAIL_COLUMNS}
    d.update(has_video=0, has_photo=0, has_gif=0, photo_count=0, video_count=0)
    return d


def store_result(conn: sqlite3.Connection, tweet_id: str, status: str, payload: Any) -> str:
    row = _blank_details()
    if status == "ok":
        row.update(parse_syndication(payload))
    else:
        row.update(status=status, error=str(payload))
    dt = snowflake_to_datetime(tweet_id)
    row.update(
        tweet_id=tweet_id,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        snowflake_created_at=dt.isoformat() if dt else None,
    )
    row.setdefault("status", status)
    row.setdefault("error", None)
    conn.execute(UPSERT_DETAILS, row)
    conn.commit()
    return row["status"]


def pending_ids(conn: sqlite3.Connection, retry_errors: bool, limit: Optional[int]) -> List[str]:
    statuses = ("pending", "error") if retry_errors else ("pending",)
    q = f"""
        SELECT l.tweet_id FROM likes l
        LEFT JOIN like_details d ON d.tweet_id = l.tweet_id
        WHERE d.tweet_id IS NULL OR d.status IN ({",".join("?" * len(statuses))})
        ORDER BY l.tweet_id DESC
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    return [r[0] for r in conn.execute(q, statuses).fetchall()]


def fetch_details(
    conn: sqlite3.Connection,
    delay: float = 1.0,
    limit: Optional[int] = None,
    retry_errors: bool = False,
) -> Dict[str, int]:
    backfill_snowflake_dates(conn)
    ids = pending_ids(conn, retry_errors, limit)
    log.info("%d tweets to fetch", len(ids))
    client = SyndicationClient(delay=delay)
    counts = {"ok": 0, "unavailable": 0, "error": 0}
    started = time.time()
    try:
        for i, tid in enumerate(ids, 1):
            status, payload = client.fetch(tid)
            final = store_result(conn, tid, status, payload)
            counts[final] = counts.get(final, 0) + 1
            if i % 25 == 0 or i == len(ids):
                elapsed = time.time() - started
                rate = i / elapsed if elapsed else 0
                eta = (len(ids) - i) / rate if rate else 0
                log.info("%d/%d  ok=%d unavailable=%d error=%d  (%.1f/s, eta %dm)",
                         i, len(ids), counts["ok"], counts["unavailable"], counts["error"], rate, eta // 60)
            client.sleep()
    except KeyboardInterrupt:
        log.warning("interrupted — progress is saved; re-run --fetch to continue")
    return counts


# --------------------------------------------------------------------------- #
# Step 4: keyword topic tagging
# --------------------------------------------------------------------------- #
# Deliberately simple: a topic matches when any pattern hits. Patterns are
# regexes matched case-insensitively against text + hashtags + url domains.
# Score = matched patterns / total patterns for that topic (so a tweet hitting
# 3 AI terms outranks one hitting a single generic word). Edit freely.
TOPIC_RULES: Dict[str, List[str]] = {
    "ai-ml": [r"\bAI\b", r"\bLLMs?\b", r"\bGPT", r"\bClaude\b", r"\bOpenAI\b", r"\bAnthropic\b", r"machine learning",
              r"\bdeep learning\b", r"\btransformers?\b", r"\bneural\b", r"\bagents?\b", r"\bRAG\b", r"\bdiffusion\b",
              r"\bCUDA\b", r"\bGPUs?\b", r"\bNVIDIA\b", r"\binference\b", r"\bfine-?tun", r"\bembeddings?\b"],
    "programming": [r"\bPython\b", r"\bRust\b", r"\bTypeScript\b", r"\bJavaScript\b", r"\bReact\b", r"\bGo(lang)?\b",
                    r"\bSQL\b", r"\bPostgres", r"\bSQLite\b", r"\bgithub\.com", r"\bopen[- ]source\b", r"\bAPI\b",
                    r"\bcompiler\b", r"\bkernel\b", r"\bLinux\b", r"\bvim\b", r"\bneovim\b", r"\bdocker\b",
                    r"\bkubernetes\b", r"\bcode\b", r"\bcoding\b", r"\bsoftware\b", r"\bengineer(ing)?\b", r"\bdev(s|elopers?)?\b"],
    "math-science": [r"\bmath(ematic)?s?\b", r"\btheorem\b", r"\bproof\b", r"\bgeometry\b", r"\btopology\b",
                     r"\bbayes(ian)?\b", r"\bprobability\b", r"\bstatistic", r"\bphysics\b", r"\bquantum\b",
                     r"\bcalculus\b", r"\blinear algebra\b", r"\bmanifold", r"\bequation", r"\barxiv\.org"],
    "space": [r"\bSpaceX\b", r"\bStarship\b", r"\bFalcon\b", r"\bNASA\b", r"\brocket", r"\borbit", r"\bMars\b",
              r"\bStarlink\b", r"\bsatellite", r"\bastronaut", r"\bJWST\b", r"\btelescope\b"],
    "politics": [r"\bTrump\b", r"\bBiden\b", r"\bHarris\b", r"\bDeSantis\b", r"\bCongress\b", r"\bSenate\b",
                 r"\belection", r"\bDemocrats?\b", r"\bRepublicans?\b", r"\bGOP\b", r"\bMAGA\b", r"\bliberal",
                 r"\bconservative", r"\bwoke\b", r"\bDOGE\b", r"\bgovernment\b", r"\bpolic(y|ies)\b", r"\bimmigra",
                 r"\bborder\b", r"\bDOJ\b", r"\bFBI\b", r"\bWhite House\b", r"\bpresident\b"],
    "geopolitics": [r"\bUkraine\b", r"\bRussia", r"\bPutin\b", r"\bChina\b", r"\bCCP\b", r"\bTaiwan\b", r"\bIsrael",
                    r"\bGaza\b", r"\bHamas\b", r"\bIran\b", r"\bNATO\b", r"\bEurope(an)?\b", r"\bEU\b", r"\bwar\b",
                    r"\bmilitary\b", r"\bPentagon\b", r"\bdrone"],
    "business-finance": [r"\bstartup", r"\bfounder", r"\bVC\b", r"\bventure\b", r"\bfundrais", r"\bIPO\b",
                         r"\brevenue\b", r"\b\$\d+[KMB]\b", r"\bARR\b", r"\bSaaS\b", r"\bmarket cap\b", r"\bstocks?\b",
                         r"\bFed\b", r"\binflation\b", r"\btariff", r"\beconom", r"\bYC\b", r"\bY Combinator\b",
                         r"\bacqui", r"\bvaluation\b"],
    "crypto": [r"\bbitcoin\b", r"\bBTC\b", r"\bethereum\b", r"\bETH\b", r"\bcrypto", r"\bblockchain\b",
               r"\bsolana\b", r"\bstablecoin", r"\bDeFi\b", r"\bNFTs?\b"],
    "miami-florida": [r"\bMiami\b", r"\bFlorida\b", r"\bBrickell\b", r"\bCoconut Grove\b", r"\bSouth Beach\b",
                      r"\bCoral Gables\b", r"\bFort Lauderdale\b", r"\bTampa\b", r"\bOrlando\b", r"\bKey West\b"],
    "real-estate-urbanism": [r"\breal estate\b", r"\bhousing\b", r"\bzoning\b", r"\bapartment", r"\bcondo",
                             r"\bmortgage", r"\brent\b", r"\burban", r"\bcity planning\b", r"\barchitect",
                             r"\btransit\b", r"\bskyline\b", r"\bdowntown\b"],
    "health-fitness": [r"\bgym\b", r"\bworkout", r"\blifting\b", r"\bprotein\b", r"\bsleep\b", r"\bfasting\b",
                       r"\bdiet\b", r"\bnutrition\b", r"\bcardio\b", r"\brunning\b", r"\blongevity\b",
                       r"\btestosterone\b", r"\bcreatine\b", r"\bhealth\b"],
    "history-culture": [r"\bhistory\b", r"\bancient\b", r"\bRoman\b", r"\bempire\b", r"\bmedieval\b", r"\bWWII\b",
                        r"\bcentur(y|ies)\b", r"\bcivilization\b", r"\bphilosoph", r"\breligio", r"\bChristian",
                        r"\bcathol", r"\bbook\b", r"\bnovel\b", r"\breading\b"],
    "humor-memes": [r"\blol\b", r"\blmao\b", r"\bmeme", r"\bshitpost", r"\bbased\b", r"😂", r"💀", r"🤣",
                    r"\bratio\b", r"\bbrainrot\b"],
    "productivity-career": [r"\bproductiv", r"\bhabit", r"\bfocus\b", r"\bcareer\b", r"\bhiring\b", r"\bjob\b",
                            r"\binterview", r"\bsalary\b", r"\bremote work\b", r"\bside project", r"\bindie hack",
                            r"\bbuild in public\b", r"\bsolopreneur\b"],
    "netherlands-dutch": [r"\bNetherlands\b", r"\bDutch\b", r"\bAmsterdam\b", r"\bHolland\b", r"\bRotterdam\b",
                          r"\bUtrecht\b", r"\bBelgi"],
}

_COMPILED_RULES = {t: [re.compile(p, re.IGNORECASE) for p in pats] for t, pats in TOPIC_RULES.items()}


def tag_text(text: str) -> Dict[str, float]:
    """Return {topic: score} for topics with at least one pattern hit."""
    out: Dict[str, float] = {}
    for topic, patterns in _COMPILED_RULES.items():
        hits = sum(1 for p in patterns if p.search(text))
        if hits:
            out[topic] = round(hits / len(patterns), 4)
    return out


def tag_topics(conn: sqlite3.Connection) -> Dict[str, int]:
    rows = conn.execute(
        """SELECT l.tweet_id,
                  COALESCE(d.text, l.full_text, '') AS text,
                  COALESCE(d.hashtags, '[]') AS hashtags,
                  COALESCE(d.url_domains, '[]') AS domains,
                  COALESCE(d.quoted_author_username, '') AS quoted
           FROM likes l LEFT JOIN like_details d ON d.tweet_id = l.tweet_id"""
    ).fetchall()
    conn.execute("DELETE FROM like_topics WHERE method = 'keyword'")
    counts: Dict[str, int] = {}
    for r in rows:
        haystack = " ".join([r["text"], " ".join(json.loads(r["hashtags"])), " ".join(json.loads(r["domains"]))])
        for topic, score in tag_text(haystack).items():
            conn.execute(
                "INSERT OR REPLACE INTO like_topics (tweet_id, topic, score, method) VALUES (?, ?, ?, 'keyword')",
                (r["tweet_id"], topic, score),
            )
            counts[topic] = counts.get(topic, 0) + 1
    conn.commit()
    counts["_tweets"] = len(rows)
    return counts


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
def print_stats(conn: sqlite3.Connection) -> None:
    def q(sql: str, *args: Any) -> List[sqlite3.Row]:
        return conn.execute(sql, args).fetchall()

    total = q("SELECT COUNT(*) c FROM likes")[0]["c"]
    print(f"likes: {total}")
    for r in q("SELECT status, COUNT(*) c FROM like_details GROUP BY status ORDER BY c DESC"):
        print(f"  {r['status']:<12} {r['c']}")
    print("media (status=ok):")
    for r in q("SELECT media_type, COUNT(*) c FROM like_details WHERE status='ok' GROUP BY media_type ORDER BY c DESC"):
        print(f"  {r['media_type']:<8} {r['c']}")
    print("top authors:")
    for r in q("SELECT author_username u, COUNT(*) c FROM like_details WHERE status='ok' GROUP BY u ORDER BY c DESC LIMIT 15"):
        print(f"  @{r['u']:<20} {r['c']}")
    print("by year (from tweet id):")
    for r in q("SELECT substr(snowflake_created_at,1,4) y, COUNT(*) c FROM like_details GROUP BY y ORDER BY y"):
        print(f"  {r['y']}  {r['c']}")
    print("topics (keyword):")
    for r in q("SELECT topic, COUNT(*) c FROM like_topics WHERE method='keyword' GROUP BY topic ORDER BY c DESC"):
        print(f"  {r['topic']:<24} {r['c']}")


# --------------------------------------------------------------------------- #
def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--load-archives", action="store_true", help="union like.js from all archive folders into likes")
    ap.add_argument("--fetch", action="store_true", help="fetch details from the syndication endpoint")
    ap.add_argument("--retry-errors", action="store_true", help="with --fetch: also retry rows with status=error")
    ap.add_argument("--limit", type=int, default=None, help="with --fetch: stop after N tweets")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (plus jitter)")
    ap.add_argument("--tag-topics", action="store_true", help="(re)run keyword topic tagging")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--all", action="store_true", help="load-archives, fetch, tag-topics, stats")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

    if args.all:
        args.load_archives = args.fetch = args.tag_topics = args.stats = True
    if not any([args.load_archives, args.fetch, args.tag_topics, args.stats]):
        ap.print_help()
        return 2

    conn = connect(args.db)
    if args.load_archives:
        s = load_archives(conn)
        n = backfill_snowflake_dates(conn)
        log.info("archives loaded: %d new likes; %d rows got snowflake dates", s["_total_new"], n)
    if args.fetch:
        c = fetch_details(conn, delay=args.delay, limit=args.limit, retry_errors=args.retry_errors)
        log.info("fetch done: %s", c)
    if args.tag_topics:
        c = tag_topics(conn)
        log.info("tagged %d tweets: %s", c.pop("_tweets"), dict(sorted(c.items(), key=lambda kv: -kv[1])))
    if args.stats:
        print_stats(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
