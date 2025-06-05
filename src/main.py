"""
Twitter Tools - Twitter Data Analysis and Management

A full-stack application for analyzing and managing Twitter/X data.
Features both a CLI interface and a REST API.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import tweepy
from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from src.settings import get_settings
from src.cache import TwitterCache, AuthCache
import time
import sqlite3

# Set up logging centrally (always INFO for startup)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Twitter Tools API",
    description="API for analyzing and managing Twitter/X data",
    version="0.1.0"
)

# Configure CORS using settings
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,  # Default: http://localhost:5173
        "http://localhost:5175",  # Alternative Vite port
        "http://localhost:5176",  # Another Vite port
        "http://localhost:3000",  # Common React dev port
        "http://127.0.0.1:5173",  # IPv4 localhost variants
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class Tweet(BaseModel):
    id: str
    text: str
    created_at: Optional[datetime] = None
    metrics: Dict[str, int]

class UserInfo(BaseModel):
    username: str
    id: str
    name: Optional[str] = None

class RateLimitInfo(BaseModel):
    is_rate_limited: bool
    reset_time: Optional[datetime] = None
    wait_seconds: Optional[int] = None
    endpoint: Optional[str] = None
    limit: Optional[int] = None  # Total requests allowed
    remaining: Optional[int] = None  # Requests remaining
    window: Optional[str] = None  # Rate limit window (e.g., "15min", "1h")

class AuthStatus(BaseModel):
    is_authenticated: bool
    username: Optional[str] = None
    error: Optional[str] = None
    can_fetch_data: bool = False
    test_tweet_count: Optional[int] = None
    rate_limit: Optional[RateLimitInfo] = None
    auth_steps: List[str] = []  # Track authentication steps
    # current_step: Optional[str] = None  # Current step being performed

class TwitterClient:
    """Singleton class to manage Twitter API client."""
    
    _instance = None
    _user_client = None  # OAuth 1.0a User Context client
    _app_client = None   # App-level Bearer Token client
    _rate_limit_info = None
    _rate_limits = {}  # Track rate limits per endpoint
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TwitterClient, cls).__new__(cls)
            cls._instance._initialize_clients()
        return cls._instance
    
    def _update_rate_limit_info(self, response, endpoint: str) -> None:
        """Update rate limit information from response headers."""
        try:
            limit = int(response.headers.get('x-rate-limit-limit', 0))
            remaining = int(response.headers.get('x-rate-limit-remaining', 0))
            reset_timestamp = int(response.headers.get('x-rate-limit-reset', 0))
            reset_time = datetime.fromtimestamp(reset_timestamp)
            wait_seconds = int((reset_time - datetime.now()).total_seconds())
            
            # Determine rate limit window (15min or 1h)
            window = "15min" if limit <= 450 else "1h"  # Twitter's typical limits
            
            self._rate_limits[endpoint] = RateLimitInfo(
                is_rate_limited=remaining == 0,
                reset_time=reset_time,
                wait_seconds=wait_seconds if remaining == 0 else 0,
                endpoint=endpoint,
                limit=limit,
                remaining=remaining,
                window=window
            )
            
            # Log rate limit status
            if remaining < limit * 0.2:  # Less than 20% remaining
                logger.warning(
                    f"Rate limit for {endpoint} ({window}): "
                    f"{remaining}/{limit} requests remaining. "
                    f"Resets at {reset_time.strftime('%H:%M:%S')}"
                )
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse rate limit headers for {endpoint}: {e}")
    
    def _handle_rate_limit(self, e: tweepy.TooManyRequests) -> None:
        """Handle rate limit exceeded error."""
        endpoint = e.response.url.split('/')[-1]
        self._update_rate_limit_info(e.response, endpoint)
        self._rate_limit_info = self._rate_limits.get(endpoint)
        
        logger.warning(
            f"Rate limit exceeded for {endpoint}. "
            f"Reset at {self._rate_limit_info.reset_time}. "
            f"Waiting {self._rate_limit_info.wait_seconds} seconds."
        )
    
    def _clear_rate_limit(self) -> None:
        """Clear rate limit information."""
        self._rate_limit_info = None
        self._rate_limits.clear()
    
    @property
    def rate_limits(self) -> Dict[str, RateLimitInfo]:
        """Get all current rate limit information."""
        return self._rate_limits
    
    def get_rate_limit(self, endpoint: str) -> Optional[RateLimitInfo]:
        """Get rate limit information for a specific endpoint."""
        return self._rate_limits.get(endpoint)
    
    def _make_request(self, client: tweepy.Client, endpoint: str, *args, **kwargs) -> Any:
        """Make an API request with rate limit tracking."""
        try:
            # Check if we're already rate limited
            rate_limit = self.get_rate_limit(endpoint)
            if rate_limit and rate_limit.is_rate_limited:
                if rate_limit.wait_seconds > 0:
                    logger.info(f"Waiting {rate_limit.wait_seconds} seconds for {endpoint} rate limit to reset...")
                    time.sleep(rate_limit.wait_seconds)
            
            # Make the request
            response = client._make_request(*args, **kwargs)
            
            # Update rate limit info from response
            self._update_rate_limit_info(response, endpoint)
            
            return response
            
        except tweepy.TooManyRequests as e:
            self._handle_rate_limit(e)
            raise
        except tweepy.TweepyException as e:
            logger.error(f"Twitter API error for {endpoint}: {str(e)}")
            raise

    def _initialize_clients(self):
        """Initialize both User Context and App-level Twitter clients."""
        settings = get_settings()
        try:
            # Initialize User Context client (OAuth 1.0a)
            logger.info("Initializing Twitter User Context client (OAuth 1.0a)...")
            cache = AuthCache()
            cred_hash = cache.hash_user_creds(
                settings.TWITTER_API_KEY,
                settings.TWITTER_API_SECRET,
                settings.TWITTER_ACCESS_TOKEN,
                settings.TWITTER_ACCESS_TOKEN_SECRET
            )
            status = cache.get_status('user_auth', cred_hash)
            if status and status['status'] == 'success':
                logger.info("User auth previously validated, skipping API call.")
                self._user_client = tweepy.Client(
                    consumer_key=settings.TWITTER_API_KEY,
                    consumer_secret=settings.TWITTER_API_SECRET,
                    access_token=settings.TWITTER_ACCESS_TOKEN,
                    access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                    return_type=dict
                )
            else:
                # Initialize User Context client (OAuth 1.0a)
                logger.info("Initializing Twitter User Context client (OAuth 1.0a)...")
                self._user_client = tweepy.Client(
                    consumer_key=settings.TWITTER_API_KEY,
                    consumer_secret=settings.TWITTER_API_SECRET,
                    access_token=settings.TWITTER_ACCESS_TOKEN,
                    access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                    return_type=dict
                )
            
            # Test User Context authentication
            try:
                me = self._user_client.get_me()
                logger.info(f"OAuth 1.0a authentication successful! Authenticated as: @{me['data']['username']}")
                self._clear_rate_limit()
                cache.set_status('user_auth', cred_hash, 'success')
            except tweepy.TooManyRequests as e:
                self._handle_rate_limit(e)
                raise
            
            # Initialize App-level client (Bearer Token)
            if settings.TWITTER_BEARER_TOKEN:
                logger.info("Initializing Twitter App-level client (Bearer Token)...")
                cache = AuthCache()
                cred_hash = cache.hash_app_creds(settings.TWITTER_BEARER_TOKEN)
                status = cache.get_status('app_auth', cred_hash)
                if status and status['status'] == 'success':
                    logger.info("App auth previously validated, skipping API call.")
                    self._app_client = tweepy.Client(
                        bearer_token=settings.TWITTER_BEARER_TOKEN,
                        return_type=dict
                    )
                else:
                    self._app_client = tweepy.Client(
                        bearer_token=settings.TWITTER_BEARER_TOKEN,
                        return_type=dict
                    )
                    # Optionally, test app auth with a lightweight call and cache result
                    try:
                        self._app_client.get_tweet("20")
                        cache.set_status('app_auth', cred_hash, 'success')
                    except Exception:
                        pass
            
        except tweepy.Unauthorized as e:
            logger.error("Authentication failed. Please check your credentials:")
            logger.error("1. Make sure your API keys and tokens are correct")
            logger.error("2. Verify that your Twitter Developer account is active")
            logger.error("3. Check if your app has the required permissions")
            logger.error("4. Verify your app's OAuth 1.0a settings in the Developer Portal")
            logger.error(f"Error details: {str(e)}")
            raise
        except tweepy.TweepyException as e:
            logger.error(f"Twitter API error: {str(e)}")
            raise

    @property
    def rate_limit_info(self) -> Optional[RateLimitInfo]:
        """Get current rate limit information."""
        return self._rate_limit_info

    @property
    def client(self) -> tweepy.Client:
        """Get the User Context client instance."""
        if not self._user_client:
            self._initialize_clients()
        return self._user_client

    @property
    def app_client(self) -> Optional[tweepy.Client]:
        """Get the App-level client instance if available."""
        if not self._app_client and get_settings().TWITTER_BEARER_TOKEN:
            self._initialize_clients()
        return self._app_client

    def get_tweet(self, tweet_id: str, use_app_auth: bool = True) -> dict:
        """Get a tweet using either App-level or User Context authentication."""
        client = self.app_client if use_app_auth and self.app_client else self.client
        return client.get_tweet(tweet_id)

    def get_users_tweets(self, user_id: str, use_app_auth: bool = True, **kwargs) -> dict:
        """Get user tweets using either App-level or User Context authentication."""
        client = self.app_client if use_app_auth and self.app_client else self.client
        return client.get_users_tweets(user_id, **kwargs)

# Dependency for FastAPI endpoints
def get_twitter_client() -> TwitterClient:
    """Dependency to get Twitter client instance."""
    return TwitterClient()

def twitter_date_to_iso(date_str):
    """Convert Twitter date string to ISO 8601 format."""
    if not date_str or date_str.strip() == '':
        return None
    try:
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.isoformat()
    except Exception:
        return None  # Return None for invalid dates

class LocalTwitterService:
    """Service class for local Twitter data operations (no API required)."""
    
    def __init__(self):
        self.console = Console()
        self.db_path = "data/x_data.db"
    
    def _get_user_id(self) -> str:
        """Get user ID from SQLite DB (assumes only one user in account table)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM account LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                raise Exception("No user found in local archive DB.")
    
    def get_users_tweets(self, user_id: str = None, **kwargs) -> Dict[str, Any]:
        """Fetch tweets from SQLite DB."""
        if user_id is None:
            user_id = self._get_user_id()
        tweets = []
        with sqlite3.connect(self.db_path) as conn:
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            cursor = conn.execute("SELECT id, text, created_at, favorite_count, retweet_count FROM tweets WHERE author_id = ? ORDER BY created_at DESC", (user_id,))
            for row in cursor.fetchall():
                tweet_id, text, created_at, favorite_count, retweet_count = row
                reply_count = reply_counts.get(tweet_id, 0)
                tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {
                        'like_count': favorite_count or 0,
                        'retweet_count': retweet_count or 0,
                        'reply_count': reply_count
                    }
                })
        return {'data': tweets, 'meta': {}}
    
    def get_recent_likes(self, count: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch likes from SQLite DB."""
        likes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tweet_id, full_text, liked_at FROM likes ORDER BY rowid DESC LIMIT ? OFFSET ?", (count, offset))
            for row in cursor.fetchall():
                tweet_id, full_text, liked_at = row
                likes.append({
                    'id': tweet_id,
                    'text': full_text or '',
                    'created_at': twitter_date_to_iso(liked_at),
                    'metrics': {
                        'like_count': 0,  # We don't have metrics for liked tweets
                        'retweet_count': 0,
                        'reply_count': 0
                    }
                })
        return likes
    
    def get_zero_engagement_tweets(self) -> List[Dict[str, Any]]:
        """Fetch zero engagement tweets from SQLite DB."""
        zero_engagement_tweets = []
        with sqlite3.connect(self.db_path) as conn:
            # Get all tweets with their engagement metrics
            cursor = conn.execute("""
                SELECT id, text, created_at, conversation_id, author_id, in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name, favorite_count, retweet_count, lang, deleted_at, status
                FROM tweets
                ORDER BY created_at DESC
            """)
            tweets = cursor.fetchall()
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            for row in tweets:
                (
                    tweet_id, text, created_at, conversation_id, author_id, in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name,
                    favorite_count, retweet_count, lang, deleted_at, status
                ) = row
                reply_count = reply_counts.get(tweet_id, 0)
                # Only include tweets with zero engagement
                if (favorite_count or 0) == 0 and (retweet_count or 0) == 0 and reply_count == 0:
                    zero_engagement_tweets.append({
                        'id': tweet_id,
                        'text': text,
                        'created_at': twitter_date_to_iso(created_at),
                        'conversation_id': conversation_id,
                        'author_id': author_id,
                        'in_reply_to_status_id': in_reply_to_status_id,
                        'in_reply_to_user_id': in_reply_to_user_id,
                        'in_reply_to_screen_name': in_reply_to_screen_name,
                        'lang': lang,
                        'deleted_at': deleted_at,
                        'status': status,
                        'metrics': {
                            'like_count': favorite_count or 0,
                            'retweet_count': retweet_count or 0,
                            'reply_count': reply_count
                        }
                    })
        return zero_engagement_tweets
    
    def get_zero_engagement_replies(self) -> List[Dict[str, Any]]:
        """Fetch zero engagement replies from SQLite DB."""
        zero_engagement_replies = []
        with sqlite3.connect(self.db_path) as conn:
            # Get all replies with their engagement metrics
            cursor = conn.execute("""
                SELECT id, text, created_at, in_reply_to_status_id, favorite_count, retweet_count
                FROM tweets
                WHERE in_reply_to_status_id IS NOT NULL
                ORDER BY created_at DESC
            """)
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            for row in cursor.fetchall():
                reply_id, text, created_at, in_reply_to, favorite_count, retweet_count = row
                reply_count = reply_counts.get(reply_id, 0)
                # Only include replies with zero engagement
                if (favorite_count or 0) == 0 and (retweet_count or 0) == 0 and reply_count == 0:
                    zero_engagement_replies.append({
                        'id': reply_id,
                        'text': text,
                        'created_at': twitter_date_to_iso(created_at),
                        'metrics': {
                            'like_count': favorite_count or 0,
                            'retweet_count': retweet_count or 0,
                            'reply_count': reply_count
                        },
                        'in_reply_to': in_reply_to or "Unknown"
                    })
        return zero_engagement_replies

    def get_bookmarks(self, count: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get bookmarks from local database."""
        try:
            logger.info(f"Fetching bookmarks with count={count}, offset={offset}")
            with sqlite3.connect(self.db_path) as conn:
                # Check if bookmarks table exists and has data
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'")
                if not cursor.fetchone():
                    logger.info("Bookmarks table does not exist")
                    return []
                
                cursor = conn.execute("""
                    SELECT id, text, created_at, author_id
                    FROM bookmarks
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (count, offset))
                
                bookmarks = []
                rows = cursor.fetchall()
                logger.info(f"Found {len(rows)} bookmarks in database")
                
                for row in rows:
                    bookmark = {
                        'id': row[0] or '',
                        'text': row[1] or '',
                        'created_at': twitter_date_to_iso(row[2]) if row[2] else None,
                        'author_id': row[3] or '',
                        'metrics': {
                            'like_count': 0,  # Bookmarks don't have engagement metrics
                            'retweet_count': 0,
                            'reply_count': 0,
                            'quote_count': 0
                        }
                    }
                    bookmarks.append(bookmark)
                
                logger.info(f"Returning {len(bookmarks)} bookmarks")
                return bookmarks
        except Exception as e:
            logger.error(f"Error fetching bookmarks: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

class TwitterService:
    """Service class for Twitter operations (requires API authentication)."""
    
    def __init__(self, client: Optional[TwitterClient] = None):
        if client is None:
            client = TwitterClient()
        self.client = client
        self.cache = TwitterCache()
        self.console = Console()
        self.db_path = "data/x_data.db"
    
    def _get_user_id(self) -> str:
        # --- OLD: Get user ID from X API ---
        # me = self.client.client.get_me()
        # return me['data']['id']
        # --- NEW: Get user ID from SQLite DB (assumes only one user in account table) ---
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM account LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                raise Exception("No user found in local archive DB.")
    
    def get_users_tweets(self, user_id: str, use_app_auth: bool = True, **kwargs) -> Dict[str, Any]:
        # --- NEW: Fetch tweets from SQLite DB ---
        tweets = []
        with sqlite3.connect(self.db_path) as conn:
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            cursor = conn.execute("SELECT id, text, created_at, favorite_count, retweet_count FROM tweets WHERE author_id = ? ORDER BY created_at DESC", (user_id,))
            for row in cursor.fetchall():
                tweet_id, text, created_at, favorite_count, retweet_count = row
                reply_count = reply_counts.get(tweet_id, 0)
                tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {
                        'like_count': favorite_count or 0,
                        'retweet_count': retweet_count or 0,
                        'reply_count': reply_count
                    }
                })
        return {'data': tweets, 'meta': {}}
    
    def get_recent_likes(self, count: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch likes from SQLite DB."""
        likes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tweet_id, full_text, liked_at FROM likes ORDER BY rowid DESC LIMIT ? OFFSET ?", (count, offset))
            for row in cursor.fetchall():
                tweet_id, full_text, liked_at = row
                likes.append({
                    'id': tweet_id,
                    'text': full_text or '',
                    'created_at': twitter_date_to_iso(liked_at),
                    'metrics': {
                        'like_count': 0,  # We don't have metrics for liked tweets
                        'retweet_count': 0,
                        'reply_count': 0
                    }
                })
        return likes
    
    def get_zero_engagement_tweets(self) -> List[Dict[str, Any]]:
        # --- NEW: Fetch zero engagement tweets from SQLite DB ---
        zero_engagement_tweets = []
        with sqlite3.connect(self.db_path) as conn:
            # Get all tweets with their engagement metrics
            cursor = conn.execute("""
                SELECT id, text, created_at, conversation_id, author_id, in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name, favorite_count, retweet_count, lang, deleted_at, status
                FROM tweets
                ORDER BY created_at DESC
            """)
            tweets = cursor.fetchall()
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            for row in tweets:
                (
                    tweet_id, text, created_at, conversation_id, author_id, in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name,
                    favorite_count, retweet_count, lang, deleted_at, status
                ) = row
                reply_count = reply_counts.get(tweet_id, 0)
                # Only include tweets with zero engagement
                if (favorite_count or 0) == 0 and (retweet_count or 0) == 0 and reply_count == 0:
                    zero_engagement_tweets.append({
                        'id': tweet_id,
                        'text': text,
                        'created_at': twitter_date_to_iso(created_at),
                        'conversation_id': conversation_id,
                        'author_id': author_id,
                        'in_reply_to_status_id': in_reply_to_status_id,
                        'in_reply_to_user_id': in_reply_to_user_id,
                        'in_reply_to_screen_name': in_reply_to_screen_name,
                        'lang': lang,
                        'deleted_at': deleted_at,
                        'status': status,
                        'metrics': {
                            'like_count': favorite_count or 0,
                            'retweet_count': retweet_count or 0,
                            'reply_count': reply_count
                        }
                    })
        return zero_engagement_tweets
    
    def get_zero_engagement_replies(self) -> List[Dict[str, Any]]:
        # --- NEW: Fetch zero engagement replies from SQLite DB ---
        zero_engagement_replies = []
        with sqlite3.connect(self.db_path) as conn:
            # Get all replies with their engagement metrics
            cursor = conn.execute("""
                SELECT id, text, created_at, in_reply_to_status_id, favorite_count, retweet_count
                FROM tweets
                WHERE in_reply_to_status_id IS NOT NULL
                ORDER BY created_at DESC
            """)
            # Build a map of tweet_id to reply count
            reply_counts = {}
            reply_cursor = conn.execute("SELECT in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL")
            for (in_reply_to_status_id,) in reply_cursor.fetchall():
                if in_reply_to_status_id:
                    reply_counts[in_reply_to_status_id] = reply_counts.get(in_reply_to_status_id, 0) + 1
            for row in cursor.fetchall():
                reply_id, text, created_at, in_reply_to, favorite_count, retweet_count = row
                reply_count = reply_counts.get(reply_id, 0)
                # Only include replies with zero engagement
                if (favorite_count or 0) == 0 and (retweet_count or 0) == 0 and reply_count == 0:
                    zero_engagement_replies.append({
                        'id': reply_id,
                        'text': text,
                        'created_at': twitter_date_to_iso(created_at),
                        'metrics': {
                            'like_count': favorite_count or 0,
                            'retweet_count': retweet_count or 0,
                            'reply_count': reply_count
                        },
                        'in_reply_to': in_reply_to or "Unknown"
                    })
        return zero_engagement_replies

    def get_bookmarks(self, count: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get bookmarks from local database."""
        try:
            logger.info(f"Fetching bookmarks with count={count}, offset={offset}")
            with sqlite3.connect(self.db_path) as conn:
                # Check if bookmarks table exists and has data
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'")
                if not cursor.fetchone():
                    logger.info("Bookmarks table does not exist")
                    return []
                
                cursor = conn.execute("""
                    SELECT id, text, created_at, author_id
                    FROM bookmarks
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (count, offset))
                
                bookmarks = []
                rows = cursor.fetchall()
                logger.info(f"Found {len(rows)} bookmarks in database")
                
                for row in rows:
                    bookmark = {
                        'id': row[0] or '',
                        'text': row[1] or '',
                        'created_at': twitter_date_to_iso(row[2]) if row[2] else None,
                        'author_id': row[3] or '',
                        'metrics': {
                            'like_count': 0,  # Bookmarks don't have engagement metrics
                            'retweet_count': 0,
                            'reply_count': 0,
                            'quote_count': 0
                        }
                    }
                    bookmarks.append(bookmark)
                
                logger.info(f"Returning {len(bookmarks)} bookmarks")
                return bookmarks
        except Exception as e:
            logger.error(f"Error fetching bookmarks: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def fetch_bookmarks_from_api(self, user_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Fetch bookmarks from Twitter API and cache them."""
        try:
            # Use the Twitter API to fetch bookmarks
            response = self.client.client.get_bookmarks(
                user_id=user_id,
                max_results=max_results,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'text']
            )
            
            bookmarks = []
            if response.data:
                for tweet in response.data:
                    bookmark = {
                        'id': tweet.id,
                        'text': tweet.text,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                        'author_id': tweet.author_id,
                        'metrics': {
                            'like_count': getattr(tweet.public_metrics, 'like_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                            'retweet_count': getattr(tweet.public_metrics, 'retweet_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                            'reply_count': getattr(tweet.public_metrics, 'reply_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                            'quote_count': getattr(tweet.public_metrics, 'quote_count', 0) if hasattr(tweet, 'public_metrics') else 0
                        }
                    }
                    bookmarks.append(bookmark)
                
                # Cache the bookmarks
                self.cache.bulk_set_bookmarks(bookmarks)
                logger.info(f"Fetched and cached {len(bookmarks)} bookmarks from API")
            
            return bookmarks
            
        except tweepy.TweepyException as e:
            logger.error(f"Error fetching bookmarks from API: {str(e)}")
            return []

# Dependencies for FastAPI endpoints
def get_local_twitter_service() -> LocalTwitterService:
    """Dependency to get local Twitter service (no API auth required)."""
    return LocalTwitterService()

def get_twitter_service(client: TwitterClient = Depends(get_twitter_client)):
    """Dependency to get Twitter service (requires API auth)."""
    return TwitterService(client=client)

# Import the in-memory cache
from src.memory_cache import cache

@app.on_event("startup")
async def startup_event():
    print("\n🚀 [Startup] Loading all Twitter data into in-memory cache...")
    cache.load_all_data()
    print(f"✅ [Startup] Cache loaded. Stats: {cache.get_stats()}")

# FastAPI endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/api/local-status")
async def local_status(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Check local data status without requiring Twitter API authentication."""
    try:
        # Test database connection and get basic stats
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM tweets")
            tweet_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM likes")
            like_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM account")
            account_count = cursor.fetchone()[0]
            
        return {
            "status": "success",
            "database_connected": True,
            "tweet_count": tweet_count,
            "like_count": like_count,
            "account_count": account_count,
            "message": "Local data is available"
        }
    except Exception as e:
        return {
            "status": "error",
            "database_connected": False,
            "error": str(e),
            "message": "Local data is not available"
        }

@app.get("/api/profile")
async def get_profile(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get user profile data from local database."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            # Try to get account info from account table first
            cursor = conn.execute("SELECT account_id, username, display_name, created_at FROM account LIMIT 1")
            account_row = cursor.fetchone()
            
            if account_row:
                user_id, username, display_name, created_at = account_row
            else:
                # If account table is empty, try to get user_id from tweets
                cursor = conn.execute("SELECT DISTINCT author_id FROM tweets LIMIT 1")
                tweet_author = cursor.fetchone()
                if tweet_author:
                    user_id = tweet_author[0]
                else:
                    user_id = "unknown"
                username = "pietertypes"
                display_name = "Pieter"
                created_at = "2024-01-01"
            # Fetch avatar_url and other profile info
            cursor = conn.execute("SELECT avatar_url, header_url, bio, website, location FROM profile WHERE account_id = ? LIMIT 1", (user_id,))
            profile_row = cursor.fetchone()
            if profile_row:
                avatar_url, header_url, bio, website, location = profile_row
            else:
                avatar_url = header_url = bio = website = location = None
            
            # Get tweet count (all tweets in personal archive are yours)
            cursor = conn.execute("SELECT COUNT(*) FROM tweets")
            tweet_count = cursor.fetchone()[0]
            
            # Get likes count
            cursor = conn.execute("SELECT COUNT(*) FROM likes")
            like_count = cursor.fetchone()[0]
            
            # Get replies count (tweets with in_reply_to_status_id)
            cursor = conn.execute("SELECT COUNT(*) FROM tweets WHERE in_reply_to_status_id IS NOT NULL AND in_reply_to_status_id != ''")
            reply_count = cursor.fetchone()[0]
            
            # Get bookmarks count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM bookmarks")
                bookmark_count = cursor.fetchone()[0]
            except:
                bookmark_count = 0
            
            # Get blocks count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM blocks")
                blocks_count = cursor.fetchone()[0]
            except:
                blocks_count = 0
            
            # Get mutes count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM mutes")
                mutes_count = cursor.fetchone()[0]
            except:
                mutes_count = 0
            
            # Get direct messages count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM direct_messages")
                dm_count = cursor.fetchone()[0]
            except:
                dm_count = 0
            
            # Get lists count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM lists")
                lists_count = cursor.fetchone()[0]
            except:
                lists_count = 0
            
            # Get following count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM users")
                following_count = cursor.fetchone()[0]
            except:
                following_count = 0
            
            # For zero engagement, we'll use the same counts since we don't have engagement metrics
            # In a real implementation, you'd filter by engagement metrics
            zero_engagement_tweets = tweet_count
            zero_engagement_replies = reply_count
            
            return {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "created_at": created_at,
                "avatar_url": avatar_url,
                "header_url": header_url,
                "bio": bio,
                "website": website,
                "location": location,
                "stats": {
                    "tweet_count": tweet_count,
                    "like_count": like_count,
                    "bookmark_count": bookmark_count,
                    "reply_count": reply_count,
                    "blocks_count": blocks_count,
                    "mutes_count": mutes_count,
                    "dm_count": dm_count,
                    "lists_count": lists_count,
                    "following_count": following_count,
                    "zero_engagement_tweets": zero_engagement_tweets,
                    "zero_engagement_replies": zero_engagement_replies
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/me", response_model=UserInfo)
async def get_me(service: TwitterService = Depends(get_twitter_service)):
    """Get authenticated user info."""
    try:
        me = service.client.client.get_me()
        return UserInfo(
            username=me.data.username,
            id=me.data.id,
            name=getattr(me.data, 'name', None)
        )
    except tweepy.TweepyException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/likes", response_model=List[Tweet])
async def get_likes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get recent likes for authenticated user."""
    return service.get_recent_likes(count=limit, offset=offset)

# Add new endpoints for zero engagement tweets and replies
@app.get("/api/tweets/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_tweets(
    service: LocalTwitterService = Depends(get_local_twitter_service),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get tweets with zero engagement, paginated."""
    tweets = service.get_zero_engagement_tweets()
    # Sort by created_at DESC, then paginate
    tweets_sorted = sorted(tweets, key=lambda t: t['created_at'], reverse=True)
    return tweets_sorted[offset:offset+limit]

@app.get("/api/replies/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_replies(
    service: LocalTwitterService = Depends(get_local_twitter_service),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get replies with zero engagement, paginated."""
    replies = service.get_zero_engagement_replies()
    replies_sorted = sorted(replies, key=lambda t: t['created_at'], reverse=True)
    return replies_sorted[offset:offset+limit]

@app.get("/api/test-auth", response_model=AuthStatus)
async def test_authentication(
    service: TwitterService = Depends(get_twitter_service)
):
    """Test Twitter API authentication and data fetching capabilities."""
    auth_steps = []
    # current_step = "Initializing authentication test..."
    
    try:
        # Remove all rate limit info and logic
        # Test OAuth 1.0a authentication
        # current_step = "Testing OAuth 1.0a authentication..."
        try:
            me = service.client.client.get_me()
            username = me['data']['username']
            auth_steps.append(f"OAuth 1.0a authentication successful as @{username}")
            
            # Test data fetching capability
            # current_step = "Testing data fetching capability..."
            try:
                tweets = service.client.get_users_tweets(
                    me['data']['id'],
                    max_results=5,  # Minimum valid value
                    tweet_fields=['created_at', 'public_metrics', 'text']
                )
                auth_steps.append("Data fetching test successful")
                
                return AuthStatus(
                    is_authenticated=True,
                    username=username,
                    can_fetch_data=True,
                    test_tweet_count=len(tweets['data']) if tweets.get('data') else 0,
                    auth_steps=auth_steps,
                )
            except tweepy.TooManyRequests as e:
                # Remove rate limit error
                return AuthStatus(
                    is_authenticated=True,
                    username=username,
                    error="Data fetching temporarily unavailable.",
                    auth_steps=auth_steps,
                )
        
        except tweepy.TooManyRequests as e:
            # Remove rate limit error
            return AuthStatus(
                is_authenticated=True,
                error="Authentication temporarily unavailable.",
                auth_steps=auth_steps,
            )
        except tweepy.Unauthorized:
            return AuthStatus(
                is_authenticated=False,
                error="OAuth 1.0a authentication failed. Please check your OAuth credentials.",
                auth_steps=auth_steps,
            )
        
    except tweepy.Forbidden as e:
        logger.error(f"Permission test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error="API permissions issue. Please check your app's permissions in the Twitter Developer Portal.",
            can_fetch_data=False,
            auth_steps=auth_steps,
        )
    except tweepy.TweepyException as e:
        logger.error(f"API test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error=f"API error: {str(e)}",
            can_fetch_data=False,
            auth_steps=auth_steps,
        )

@app.get("/api/following")
async def get_following(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get accounts the user is following."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, username, display_name, user_link
                FROM users
                ORDER BY display_name
            """)
            following = [
                {
                    "id": row[0],
                    "username": row[1],
                    "display_name": row[2],
                    "avatar_url": None  # Optionally add avatar if available
                }
                for row in cursor.fetchall()
            ]
        return following
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/followers")
async def get_followers(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get accounts that follow the user."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, username, display_name, user_link
                FROM users
                ORDER BY display_name
            """)
            followers = [
                {
                    "id": row[0],
                    "username": row[1],
                    "display_name": row[2],
                    "avatar_url": None  # Optionally add avatar if available
                }
                for row in cursor.fetchall()
            ]
        return followers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tweet/delete")
async def delete_tweet(
    tweet_id: str = Body(..., embed=True),
    service: TwitterService = Depends(get_twitter_service)
):
    """Delete a tweet via X API, then mark as deleted in the local DB if successful."""
    try:
        # Delete from X API (Twitter)
        client = service.client.client
        resp = client.delete_tweet(tweet_id)
        if resp and (getattr(resp, 'data', None) and resp.data.get('deleted')):
            # Mark as deleted in local DB
            with sqlite3.connect(service.db_path) as conn:
                conn.execute("UPDATE tweets SET status = 'deleted' WHERE id = ?", (tweet_id,))
                conn.commit()
            return {"success": True, "message": "Tweet deleted on X and marked as deleted locally."}
        else:
            return {"success": False, "message": "Failed to delete tweet on X. Not marked as deleted locally."}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/api/bookmarks", response_model=List[Tweet])
async def get_bookmarks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get bookmarks for authenticated user."""
    logger.info(f"Fetching bookmarks with count={limit}, offset={offset}")
    return service.get_bookmarks(count=limit, offset=offset)

@app.get("/api/blocks")
async def get_blocks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get blocked users."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, user_link
                FROM blocks
                ORDER BY user_id
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            blocks = []
            for row in cursor.fetchall():
                blocks.append({
                    "user_id": row[0],
                    "user_link": row[1],
                    "username": row[1].split('/')[-1] if row[1] else row[0]  # Extract username from link
                })
            
            return blocks
    except Exception as e:
        logger.error(f"Error fetching blocks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mutes")
async def get_mutes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get muted users."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, user_link
                FROM mutes
                ORDER BY user_id
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            mutes = []
            for row in cursor.fetchall():
                mutes.append({
                    "user_id": row[0],
                    "user_link": row[1],
                    "username": row[1].split('/')[-1] if row[1] else row[0]  # Extract username from link
                })
            
            return mutes
    except Exception as e:
        logger.error(f"Error fetching mutes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/direct-messages")
async def get_direct_messages(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get direct messages."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            # Check if direct_messages table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='direct_messages'
            """)
            
            if not cursor.fetchone():
                return []  # Table doesn't exist, return empty list
            
            cursor = conn.execute("""
                SELECT message_id, conversation_id, sender_id, recipient_id, 
                       text, created_at, media_url
                FROM direct_messages
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "message_id": row[0],
                    "conversation_id": row[1],
                    "sender_id": row[2],
                    "recipient_id": row[3],
                    "text": row[4],
                    "created_at": row[5],
                    "media_url": row[6]
                })
            
            return messages
    except Exception as e:
        logger.error(f"Error fetching direct messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lists")
async def get_lists(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get Twitter lists."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, name, url, type
                FROM lists
                ORDER BY name
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            lists = []
            for row in cursor.fetchall():
                lists.append({
                    "id": row[0],
                    "name": row[1],
                    "url": row[2],
                    "type": row[3]
                })
            
            return lists
    except Exception as e:
        logger.error(f"Error fetching lists: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# CLI functionality
def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Twitter Tools CLI')
    parser.add_argument(
        '-n', '--number',
        type=int,
        default=10,
        help='Number of recent likes to fetch (default: 10)'
    )
    args = parser.parse_args()
    
    try:
        service = TwitterService()
        likes = service.get_recent_likes(count=args.number)
        service.display_likes(likes)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise SystemExit(1)

if __name__ == "__main__":
    main() 