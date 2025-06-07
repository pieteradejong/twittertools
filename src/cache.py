"""
Twitter Data Cache Module

This module provides caching functionality for Twitter data to minimize API calls.
It uses SQLite to store cached data with appropriate TTL (Time To Live) values.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import hashlib

logger = logging.getLogger(__name__)

AUTH_CACHE_PATH = Path(__file__).parent.parent / 'data' / 'auth_cache.json'

class TwitterCache:
    """Manages caching of Twitter data to minimize API calls."""
    
    _instance = None
    _initialized = False
    
    # Cache TTLs (Time To Live) in seconds
    TTL = {
        'tweet': 24 * 60 * 60,  # 24 hours for tweets
        'user': 24 * 60 * 60,   # 24 hours for user data
        'like': 1 * 60 * 60,    # 1 hour for likes
        'bookmark': 1 * 60 * 60, # 1 hour for bookmarks
        'reply': 24 * 60 * 60,  # 24 hours for replies
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TwitterCache, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._db_path = Path(__file__).parent.parent / 'data' / 'twitter_cache.db'
            self._db_path.parent.mkdir(exist_ok=True)
            self._init_db()
            self._initialized = True
    
    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tweets (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS likes (
                    tweet_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    tweet_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS replies (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            # Add last_fetch table to track fetch times
            conn.execute("""
                CREATE TABLE IF NOT EXISTS last_fetch (
                    user_id TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    last_fetch_time TIMESTAMP NOT NULL,
                    PRIMARY KEY (user_id, data_type)
                )
            """)
            
            # Create indexes for faster lookups
            for table in ['tweets', 'users', 'likes', 'bookmarks', 'replies']:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_expires_at ON {table}(expires_at)")
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self._db_path)
    
    def _cleanup_expired(self, table: str):
        """Remove expired entries from the specified table."""
        with self._get_conn() as conn:
            conn.execute(f"DELETE FROM {table} WHERE expires_at < ?", (datetime.now(),))
    
    def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a tweet from cache if available and not expired."""
        self._cleanup_expired('tweets')
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data FROM tweets WHERE id = ? AND expires_at > ?",
                (tweet_id, datetime.now())
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
    
    def set_tweet(self, tweet_id: str, data: Dict[str, Any]):
        """Cache a tweet with appropriate TTL."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['tweet'])
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tweets (id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tweet_id, json.dumps(data), now, now, expires_at)
            )
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data from cache if available and not expired."""
        self._cleanup_expired('users')
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data FROM users WHERE id = ? AND expires_at > ?",
                (user_id, datetime.now())
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
    
    def set_user(self, user_id: str, data: Dict[str, Any]):
        """Cache user data with appropriate TTL."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['user'])
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO users (id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, json.dumps(data), now, now, expires_at)
            )
    
    def get_like(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a like from cache if available and not expired."""
        self._cleanup_expired('likes')
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data FROM likes WHERE tweet_id = ? AND expires_at > ?",
                (tweet_id, datetime.now())
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
    
    def set_like(self, tweet_id: str, data: Dict[str, Any]):
        """Cache a like with appropriate TTL."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['like'])
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO likes (tweet_id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tweet_id, json.dumps(data), now, now, expires_at)
            )
    
    def get_bookmark(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a bookmark from cache if available and not expired."""
        self._cleanup_expired('bookmarks')
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data FROM bookmarks WHERE tweet_id = ? AND expires_at > ?",
                (tweet_id, datetime.now())
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
    
    def set_bookmark(self, tweet_id: str, data: Dict[str, Any]):
        """Cache a bookmark with appropriate TTL."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['bookmark'])
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO bookmarks (tweet_id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tweet_id, json.dumps(data), now, now, expires_at)
            )
    
    def get_reply(self, reply_id: str) -> Optional[Dict[str, Any]]:
        """Get a reply from cache if available and not expired."""
        self._cleanup_expired('replies')
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT data FROM replies WHERE id = ? AND expires_at > ?",
                (reply_id, datetime.now())
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
    
    def set_reply(self, reply_id: str, data: Dict[str, Any]):
        """Cache a reply with appropriate TTL."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['reply'])
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO replies (id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (reply_id, json.dumps(data), now, now, expires_at)
            )
    
    def bulk_set_tweets(self, tweets: List[Dict[str, Any]]):
        """Cache multiple tweets efficiently."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['tweet'])
        with self._get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO tweets (id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(tweet['id'], json.dumps(tweet), now, now, expires_at) for tweet in tweets]
            )
    
    def bulk_set_replies(self, replies: List[Dict[str, Any]]):
        """Cache multiple replies efficiently."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['reply'])
        with self._get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO replies (id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(reply['id'], json.dumps(reply), now, now, expires_at) for reply in replies]
            )
    
    def bulk_set_bookmarks(self, bookmarks: List[Dict[str, Any]]):
        """Cache multiple bookmarks efficiently."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.TTL['bookmark'])
        with self._get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO bookmarks (tweet_id, data, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(bookmark['id'], json.dumps(bookmark), now, now, expires_at) for bookmark in bookmarks]
            )
    
    def get_last_fetch_time(self, user_id: str, data_type: str) -> Optional[datetime]:
        """Get the last fetch time for a specific user and data type."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT last_fetch_time FROM last_fetch WHERE user_id = ? AND data_type = ?",
                (user_id, data_type)
            )
            result = cursor.fetchone()
            return datetime.fromisoformat(result[0]) if result else None
    
    def update_last_fetch_time(self, user_id: str, data_type: str, fetch_time: datetime):
        """Update the last fetch time for a specific user and data type."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO last_fetch (user_id, data_type, last_fetch_time)
                VALUES (?, ?, ?)
                """,
                (user_id, data_type, fetch_time.isoformat())
            )
    
    def get_user_tweets_since(self, user_id: str, since_time: datetime) -> List[Dict[str, Any]]:
        """Get all cached tweets for a user since a specific time."""
        self._cleanup_expired('tweets')
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT data FROM tweets 
                WHERE json_extract(data, '$.author_id') = ? 
                AND json_extract(data, '$.created_at') > ?
                AND expires_at > ?
                ORDER BY json_extract(data, '$.created_at') DESC
                """,
                (user_id, since_time.isoformat(), datetime.now())
            )
            return [json.loads(row[0]) for row in cursor.fetchall()]
    
    def get_user_likes_since(self, user_id: str, since_time: datetime) -> List[Dict[str, Any]]:
        """Get all cached likes for a user since a specific time."""
        self._cleanup_expired('likes')
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT data FROM likes 
                WHERE json_extract(data, '$.user_id') = ? 
                AND json_extract(data, '$.liked_at') > ?
                AND expires_at > ?
                ORDER BY json_extract(data, '$.liked_at') DESC
                """,
                (user_id, since_time.isoformat(), datetime.now())
            )
            return [json.loads(row[0]) for row in cursor.fetchall()]
    
    def get_user_replies_since(self, user_id: str, since_time: datetime) -> List[Dict[str, Any]]:
        """Get all cached replies for a user since a specific time."""
        self._cleanup_expired('replies')
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT data FROM replies 
                WHERE json_extract(data, '$.author_id') = ? 
                AND json_extract(data, '$.created_at') > ?
                AND expires_at > ?
                ORDER BY json_extract(data, '$.created_at') DESC
                """,
                (user_id, since_time.isoformat(), datetime.now())
            )
            return [json.loads(row[0]) for row in cursor.fetchall()]

class AuthCache:
    """Caches the validity of Twitter credentials by hash, never storing secrets."""
    def __init__(self):
        self.path = AUTH_CACHE_PATH
        self._cache = self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"user_auth": {}, "app_auth": {}}

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self._cache, f, indent=2)

    @staticmethod
    def hash_user_creds(api_key, api_secret, access_token, access_token_secret):
        combo = f"{api_key}:{api_secret}:{access_token}:{access_token_secret}"
        return hashlib.sha256(combo.encode()).hexdigest()

    @staticmethod
    def hash_app_creds(bearer_token):
        return hashlib.sha256(bearer_token.encode()).hexdigest()

    def get_status(self, auth_type, cred_hash):
        return self._cache.get(auth_type, {}).get(cred_hash)

    def set_status(self, auth_type, cred_hash, status):
        self._cache.setdefault(auth_type, {})[cred_hash] = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save() 