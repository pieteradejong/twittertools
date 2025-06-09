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
import json

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
class Author(BaseModel):
    id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    verified: bool = False

class Tweet(BaseModel):
    id: str
    text: str
    created_at: Optional[datetime] = None
    metrics: Dict[str, int]
    author: Optional[Author] = None

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
        """Fetch likes from SQLite DB with author information."""
        likes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT tweet_id, full_text, liked_at, author_id, author_username 
                FROM likes 
                ORDER BY rowid DESC 
                LIMIT ? OFFSET ?
            """, (count, offset))
            
            for row in cursor.fetchall():
                tweet_id, full_text, liked_at, author_id, author_username = row
                likes.append({
                    'id': tweet_id,
                    'text': full_text or '',
                    'created_at': twitter_date_to_iso(liked_at),
                    'author_id': author_id,
                    'author_username': author_username,
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
                    # Get author information
                    author_cursor = conn.execute("""
                        SELECT a.username, a.display_name, p.avatar_url 
                        FROM account a 
                        LEFT JOIN profile p ON a.account_id = p.account_id 
                        WHERE a.account_id = ?
                    """, (author_id,))
                    author_row = author_cursor.fetchone()
                    
                    if author_row:
                        username, display_name, avatar_url = author_row
                        user_info = {
                            'id': author_id,
                            'username': username,
                            'display_name': display_name,
                            'avatar_url': avatar_url,
                            'verified': False
                        }
                    else:
                        user_info = {
                            'id': author_id,
                            'username': 'pietertypes',
                            'display_name': 'Pieter',
                            'avatar_url': None,
                            'verified': False
                        }
                    
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
                        'author': user_info,
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
                SELECT id, text, created_at, in_reply_to_status_id, favorite_count, retweet_count, author_id
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
                reply_id, text, created_at, in_reply_to, favorite_count, retweet_count, author_id = row
                reply_count = reply_counts.get(reply_id, 0)
                # Only include replies with zero engagement
                if (favorite_count or 0) == 0 and (retweet_count or 0) == 0 and reply_count == 0:
                    # Get author information
                    author_cursor = conn.execute("""
                        SELECT a.username, a.display_name, p.avatar_url 
                        FROM account a 
                        LEFT JOIN profile p ON a.account_id = p.account_id 
                        WHERE a.account_id = ?
                    """, (author_id,))
                    author_row = author_cursor.fetchone()
                    
                    if author_row:
                        username, display_name, avatar_url = author_row
                        user_info = {
                            'id': author_id,
                            'username': username,
                            'display_name': display_name,
                            'avatar_url': avatar_url,
                            'verified': False
                        }
                    else:
                        user_info = {
                            'id': author_id,
                            'username': 'pietertypes',
                            'display_name': 'Pieter',
                            'avatar_url': None,
                            'verified': False
                        }
                    
                    zero_engagement_replies.append({
                        'id': reply_id,
                        'text': text,
                        'created_at': twitter_date_to_iso(created_at),
                        'author': user_info,
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
            
            # Get author information once
            author_cursor = conn.execute("""
                SELECT a.username, a.display_name, p.avatar_url 
                FROM account a 
                LEFT JOIN profile p ON a.account_id = p.account_id 
                WHERE a.account_id = ?
            """, (user_id,))
            author_row = author_cursor.fetchone()
            
            if author_row:
                username, display_name, avatar_url = author_row
                user_info = {
                    'id': user_id,
                    'username': username,
                    'display_name': display_name,
                    'avatar_url': avatar_url,
                    'verified': False
                }
            else:
                user_info = {
                    'id': user_id,
                    'username': 'pietertypes',
                    'display_name': 'Pieter',
                    'avatar_url': None,
                    'verified': False
                }
            
            for row in cursor.fetchall():
                tweet_id, text, created_at, favorite_count, retweet_count = row
                reply_count = reply_counts.get(tweet_id, 0)
                tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'author': user_info,
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
    """Get recent likes for authenticated user with author information."""
    
    # Get basic likes data
    likes = service.get_recent_likes(count=limit, offset=offset)
    
    # Add basic author information for likes
    for like in likes:
        if not like.get('author'):
            # Try to get author info if we have it, otherwise use fallback
            like['author'] = {
                'id': like.get('author_id'),
                'username': like.get('author_username') or 'unknown',
                'display_name': like.get('author_username') or 'Unknown User',
                'avatar_url': None,
                'verified': False
            }
    
    return likes

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
async def get_following(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get accounts the user is following."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            # Get current user ID
            cursor = conn.execute("SELECT account_id FROM account LIMIT 1")
            user_row = cursor.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User account not found")
            user_id = user_row[0]
            
            # Check if we have the new relationships table
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationships'")
            has_relationships_table = cursor.fetchone() is not None
            
            if has_relationships_table:
                # Use the new relationships table
                cursor = conn.execute("""
                    SELECT 
                        r.target_user_id,
                        u.username,
                        u.display_name,
                        u.user_link,
                        u.avatar_url,
                        u.verified,
                        u.follower_count,
                        u.following_count,
                        u.tweet_count,
                        r.created_at as relationship_created_at
                    FROM relationships r
                    LEFT JOIN users u ON r.target_user_id = u.id
                    WHERE r.source_user_id = ? AND r.relationship_type = 'following'
                    ORDER BY u.display_name, r.target_user_id
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                
                # Get total count
                cursor_count = conn.execute("""
                    SELECT COUNT(*) FROM relationships 
                    WHERE source_user_id = ? AND relationship_type = 'following'
                """, (user_id,))
                total_count = cursor_count.fetchone()[0]
            else:
                # Fallback to the old users table approach
                cursor = conn.execute("""
                    SELECT 
                        u.id,
                        u.username,
                        u.display_name,
                        u.user_link,
                        u.avatar_url,
                        u.verified,
                        u.follower_count,
                        u.following_count,
                        u.tweet_count,
                        NULL as relationship_created_at
                    FROM users u
                    ORDER BY u.display_name, u.id
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                # Get total count
                cursor_count = conn.execute("SELECT COUNT(*) FROM users")
                total_count = cursor_count.fetchone()[0]
            
            following = []
            for row in cursor.fetchall():
                following.append({
                    "id": row[0],
                    "username": row[1] or f"user_{row[0][-8:]}",
                    "display_name": row[2] or f"User {row[0][-8:]}",
                    "user_link": row[3],
                    "avatar_url": row[4],
                    "verified": bool(row[5]) if row[5] is not None else False,
                    "follower_count": row[6],
                    "following_count": row[7],
                    "tweet_count": row[8],
                    "relationship_created_at": row[9]
                })
            
            return {
                "following": following,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/followers")
async def get_followers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get accounts that follow the user."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            # Get current user ID
            cursor = conn.execute("SELECT account_id FROM account LIMIT 1")
            user_row = cursor.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User account not found")
            user_id = user_row[0]
            
            # Check if we have the new relationships table
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationships'")
            has_relationships_table = cursor.fetchone() is not None
            
            if has_relationships_table:
                # Use the new relationships table
                cursor = conn.execute("""
                    SELECT 
                        r.source_user_id,
                        u.username,
                        u.display_name,
                        u.user_link,
                        u.avatar_url,
                        u.verified,
                        u.follower_count,
                        u.following_count,
                        u.tweet_count,
                        r.created_at as relationship_created_at
                    FROM relationships r
                    LEFT JOIN users u ON r.source_user_id = u.id
                    WHERE r.target_user_id = ? AND r.relationship_type = 'follower'
                    ORDER BY u.display_name, r.source_user_id
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                
                # Get total count
                cursor_count = conn.execute("""
                    SELECT COUNT(*) FROM relationships 
                    WHERE target_user_id = ? AND relationship_type = 'follower'
                """, (user_id,))
                total_count = cursor_count.fetchone()[0]
            else:
                # Fallback: return empty list since we can't distinguish followers from following without relationships table
                return {
                    "followers": [],
                    "total_count": 0,
                    "limit": limit,
                    "offset": offset,
                    "message": "Relationships data not available. Please reload data with updated schema."
                }
            
            followers = []
            for row in cursor.fetchall():
                followers.append({
                    "id": row[0],
                    "username": row[1] or f"user_{row[0][-8:]}",
                    "display_name": row[2] or f"User {row[0][-8:]}",
                    "user_link": row[3],
                    "avatar_url": row[4],
                    "verified": bool(row[5]) if row[5] is not None else False,
                    "follower_count": row[6],
                    "following_count": row[7],
                    "tweet_count": row[8],
                    "relationship_created_at": row[9]
                })
            
            return {
                "followers": followers,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
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

# Semantic filtering endpoints
@app.get("/api/likes/topics")
async def get_available_topics():
    """Get all available topics with their tweet counts."""
    try:
        from .semantic_classifier import SemanticTweetClassifier
        classifier = SemanticTweetClassifier()
        topics = classifier.get_available_topics()
        return {"topics": topics}
    except Exception as e:
        logger.error(f"Error getting topics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/likes/by-topic/{topic}")
async def get_likes_by_topic(
    topic: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.3, ge=0.0, le=1.0)
):
    """Get likes filtered by semantic topic."""
    try:
        from .semantic_classifier import SemanticTweetClassifier
        classifier = SemanticTweetClassifier()
        results = classifier.get_tweets_by_topic(topic, min_score, limit, offset)
        
        # Convert to Tweet format
        tweets = []
        for result in results:
            tweets.append({
                'id': result['tweet_id'],
                'text': result['text'],
                'created_at': None,  # We don't have this in classifications
                'metrics': {
                    'like_count': 0,
                    'retweet_count': 0,
                    'reply_count': 0
                },
                'semantic_score': result['score'],
                'topic': result['topic']
            })
        
        return tweets
    except Exception as e:
        logger.error(f"Error getting likes by topic: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/likes/search")
async def search_likes_semantic(
    query: str = Query(..., description="Semantic search query"),
    limit: int = Query(20, ge=1, le=100)
):
    """Search likes using semantic similarity."""
    try:
        from .semantic_classifier import SemanticTweetClassifier
        classifier = SemanticTweetClassifier()
        results = classifier.search_tweets_semantic(query, limit)
        
        # Convert to Tweet format
        tweets = []
        for result in results:
            tweets.append({
                'id': result['tweet_id'],
                'text': result['text'],
                'created_at': None,
                'metrics': {
                    'like_count': 0,
                    'retweet_count': 0,
                    'reply_count': 0
                },
                'similarity_score': result['similarity_score']
            })
        
        return tweets
    except Exception as e:
        logger.error(f"Error searching likes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/classify/run")
async def run_classification():
    """Trigger classification of all tweets and likes."""
    try:
        from .semantic_classifier import classify_all_likes, classify_all_tweets
        
        # Run classification in background (for production, use a task queue)
        import threading
        
        def run_classification_task():
            classify_all_tweets()
            classify_all_likes()
        
        thread = threading.Thread(target=run_classification_task)
        thread.start()
        
        return {"message": "Classification started in background", "status": "running"}
    except Exception as e:
        logger.error(f"Error starting classification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/enrichment/stats")
async def get_enrichment_stats(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get tweet enrichment statistics."""
    try:
        from .tweet_enrichment_service import TweetEnrichmentService
        enrichment_service = TweetEnrichmentService(service.db_path)
        stats = enrichment_service.get_enrichment_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting enrichment stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrichment/run")
async def run_enrichment(
    limit: int = Query(100, ge=1, le=1000, description="Number of likes to enrich"),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Trigger enrichment of likes with author information from Twitter API."""
    try:
        from .tweet_enrichment_service import TweetEnrichmentService
        
        # Get likes that need enrichment
        likes = service.get_recent_likes(count=limit, offset=0)
        
        # Enrich them
        enrichment_service = TweetEnrichmentService(service.db_path)
        enriched_likes = enrichment_service.enrich_likes_batch(likes)
        
        # Update the likes table
        updated_count = enrichment_service.update_likes_table_with_enrichment()
        
        return {
            "message": f"Enriched {len(enriched_likes)} likes",
            "processed": len(enriched_likes),
            "updated_in_db": updated_count,
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"Error running enrichment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrichment/text-patterns")
async def run_text_pattern_enrichment(
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Run text-based pattern enrichment for tweet authors."""
    try:
        from .text_based_enrichment import TextBasedEnrichmentService
        
        text_service = TextBasedEnrichmentService(service.db_path)
        enriched_count = text_service.enrich_likes_from_text()
        
        return {
            "message": "Text pattern enrichment completed",
            "enriched_count": enriched_count,
            "method": "text_patterns"
        }
        
    except Exception as e:
        logger.error(f"Text pattern enrichment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrichment/web-scraping")
async def run_web_scraping_enrichment(
    limit: int = Query(50, ge=1, le=100, description="Number of tweets to scrape"),
    delay: float = Query(2.0, ge=1.0, le=10.0, description="Delay between requests in seconds"),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Run web scraping enrichment for tweet authors."""
    try:
        from .web_scraping_enrichment import WebScrapingEnrichmentService
        
        scraping_service = WebScrapingEnrichmentService(service.db_path)
        enriched_count = scraping_service.enrich_likes_batch(limit=limit, delay=delay)
        
        return {
            "message": "Web scraping enrichment completed",
            "enriched_count": enriched_count,
            "method": "web_scraping",
            "processed_limit": limit
        }
        
    except Exception as e:
        logger.error(f"Web scraping enrichment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrichment/multi-method")
async def run_multi_method_enrichment(
    limit: int = Query(100, ge=1, le=500, description="Number of tweets to process"),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Run multi-method enrichment using API, Nitter, and text patterns."""
    try:
        from .alternative_api_enrichment import AlternativeAPIEnrichmentService
        
        multi_service = AlternativeAPIEnrichmentService(service.db_path)
        stats = multi_service.enrich_with_multiple_methods(limit=limit)
        
        return {
            "message": "Multi-method enrichment completed",
            "stats": stats,
            "method": "multi_method"
        }
        
    except Exception as e:
        logger.error(f"Multi-method enrichment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    """Get Twitter lists with enriched metadata."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            # Join with list metadata cache to get member counts
            cursor = conn.execute("""
                SELECT 
                    l.id, 
                    l.name, 
                    l.url, 
                    l.type,
                    lmc.member_count,
                    lmc.follower_count,
                    lmc.description,
                    lmc.private
                FROM lists l
                LEFT JOIN list_metadata_cache lmc ON l.id = lmc.list_id 
                    AND lmc.expires_at > datetime('now')
                ORDER BY l.name IS NULL, l.name, l.id
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            lists = []
            for row in cursor.fetchall():
                list_data = {
                    "id": row[0],
                    "name": row[1],
                    "url": row[2],
                    "type": row[3],
                    "member_count": row[4],
                    "follower_count": row[5],
                    "description": row[6],
                    "private": bool(row[7]) if row[7] is not None else None
                }
                lists.append(list_data)
            
            return lists
    except Exception as e:
        logger.error(f"Error fetching lists: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lists/enrichment/stats")
async def get_list_enrichment_stats(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get statistics about list enrichment."""
    try:
        from .list_enrichment_service import ListEnrichmentService
        
        enrichment_service = ListEnrichmentService(service.db_path)
        stats = enrichment_service.get_enrichment_stats()
        
        return stats
    except Exception as e:
        logger.error(f"Error getting list enrichment stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lists/enrichment/run")
async def run_list_enrichment(
    limit: int = Query(10, ge=1, le=50, description="Number of lists to enrich"),
    delay: float = Query(1.0, ge=0.5, le=5.0, description="Delay between API requests in seconds"),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Run list enrichment to fetch member counts from Twitter API."""
    try:
        from .list_enrichment_service import ListEnrichmentService
        
        enrichment_service = ListEnrichmentService(service.db_path)
        
        # Get list IDs to enrich
        all_list_ids = enrichment_service.get_all_list_ids()
        list_ids_to_enrich = all_list_ids[:limit]  # Limit the number for safety
        
        if not list_ids_to_enrich:
            return {
                "message": "No lists found to enrich",
                "stats": {"enriched_count": 0, "failed_count": 0, "cached_count": 0, "total_processed": 0}
            }
        
        # Run enrichment
        stats = enrichment_service.enrich_lists_batch(list_ids_to_enrich, delay=delay)
        
        return {
            "message": f"List enrichment completed for {len(list_ids_to_enrich)} lists",
            "stats": stats,
            "processed_list_ids": list_ids_to_enrich
        }
        
    except Exception as e:
        logger.error(f"List enrichment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# COMPREHENSIVE X API ENDPOINTS
# ============================================================================

@app.get("/api/comprehensive/stats")
async def get_comprehensive_api_stats():
    """Get statistics about all comprehensive API data."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        stats = service.get_cached_data_stats()
        api_usage = service.get_api_usage_stats(hours=24)
        
        return {
            "cached_data": stats,
            "api_usage_24h": api_usage,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting comprehensive API stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/tweets")
async def fetch_comprehensive_tweets(
    user_id: str = Query(..., description="User ID to fetch tweets for"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of tweets to fetch")
):
    """Fetch comprehensive tweet data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_tweets(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched tweets for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive tweets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/likes")
async def fetch_comprehensive_likes(
    user_id: str = Query(..., description="User ID to fetch likes for"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of likes to fetch")
):
    """Fetch comprehensive likes data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_likes(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched likes for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive likes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/bookmarks")
async def fetch_comprehensive_bookmarks(
    user_id: str = Query(..., description="User ID to fetch bookmarks for"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of bookmarks to fetch")
):
    """Fetch comprehensive bookmarks data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_bookmarks(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched bookmarks for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive bookmarks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/followers")
async def fetch_comprehensive_followers(
    user_id: str = Query(..., description="User ID to fetch followers for"),
    max_results: int = Query(1000, ge=1, le=1000, description="Maximum number of followers to fetch")
):
    """Fetch comprehensive followers data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_followers(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched followers for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive followers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/following")
async def fetch_comprehensive_following(
    user_id: str = Query(..., description="User ID to fetch following for"),
    max_results: int = Query(1000, ge=1, le=1000, description="Maximum number of following to fetch")
):
    """Fetch comprehensive following data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_following(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched following for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive following: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/lists")
async def fetch_comprehensive_lists(
    user_id: str = Query(..., description="User ID to fetch lists for"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of lists to fetch")
):
    """Fetch comprehensive lists data from X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_user_lists(user_id=user_id, max_results=max_results)
        
        return {
            "message": f"Fetched lists for user {user_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive lists: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/search/tweets/recent")
async def search_comprehensive_tweets_recent(
    query: str = Query(..., description="Search query for tweets"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of tweets to fetch")
):
    """Search recent tweets (last 7 days) using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.search_tweets_recent(query=query, max_results=max_results)
        
        return {
            "message": f"Searched recent tweets for query: {query}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error searching comprehensive tweets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/search/tweets/all")
async def search_comprehensive_tweets_all(
    query: str = Query(..., description="Search query for tweets"),
    max_results: int = Query(500, ge=1, le=500, description="Maximum number of tweets to fetch")
):
    """Search all tweets (full archive) using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.search_tweets_all(query=query, max_results=max_results)
        
        return {
            "message": f"Searched all tweets for query: {query}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error searching comprehensive tweets (all): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/spaces")
async def fetch_comprehensive_spaces(
    query: str = Query(None, description="Search query for Spaces"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of Spaces to fetch")
):
    """Fetch or search Spaces using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_spaces(query=query, max_results=max_results)
        
        return {
            "message": f"Fetched Spaces" + (f" for query: {query}" if query else ""),
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/direct-messages")
async def fetch_comprehensive_direct_messages(
    participant_id: str = Query(..., description="Participant ID for DM conversation"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of messages to fetch")
):
    """Fetch direct messages using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_direct_messages(participant_id=participant_id, max_results=max_results)
        
        return {
            "message": f"Fetched direct messages with participant {participant_id}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive direct messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/search/communities")
async def search_comprehensive_communities(
    query: str = Query(..., description="Search query for communities"),
    max_results: int = Query(100, ge=1, le=100, description="Maximum number of communities to fetch")
):
    """Search communities using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.search_communities(query=query, max_results=max_results)
        
        return {
            "message": f"Searched communities for query: {query}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error searching comprehensive communities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comprehensive/fetch/trends")
async def fetch_comprehensive_trends(
    woeid: int = Query(1, description="Where On Earth ID (1 = worldwide)")
):
    """Fetch trending topics using comprehensive X API."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        result = service.fetch_trends(woeid=woeid)
        
        return {
            "message": f"Fetched trends for WOEID: {woeid}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching comprehensive trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/comprehensive/data/tweets")
async def get_comprehensive_tweets_data(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    author_id: str = Query(None, description="Filter by author ID")
):
    """Get stored comprehensive tweets data."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        
        with sqlite3.connect(service.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            where_clause = ""
            params = []
            
            if author_id:
                where_clause = "WHERE author_id = ?"
                params.append(author_id)
            
            query = f"""
                SELECT id, text, created_at, author_id, conversation_id, 
                       public_metrics, lang, cached_at, data_source
                FROM tweets_comprehensive 
                {where_clause}
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor = conn.execute(query, params)
            tweets = [dict(row) for row in cursor.fetchall()]
            
            # Parse JSON fields
            for tweet in tweets:
                if tweet['public_metrics']:
                    tweet['public_metrics'] = json.loads(tweet['public_metrics'])
            
            return tweets
    except Exception as e:
        logger.error(f"Error getting comprehensive tweets data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/comprehensive/data/users")
async def get_comprehensive_users_data(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    username: str = Query(None, description="Filter by username")
):
    """Get stored comprehensive users data."""
    try:
        from .comprehensive_x_api_service import ComprehensiveXAPIService
        
        service = ComprehensiveXAPIService()
        
        with sqlite3.connect(service.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            where_clause = ""
            params = []
            
            if username:
                where_clause = "WHERE username LIKE ?"
                params.append(f"%{username}%")
            
            query = f"""
                SELECT id, username, name, description, location, url,
                       profile_image_url, verified, created_at, public_metrics,
                       cached_at, data_source
                FROM users_comprehensive 
                {where_clause}
                ORDER BY username 
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor = conn.execute(query, params)
            users = [dict(row) for row in cursor.fetchall()]
            
            # Parse JSON fields
            for user in users:
                if user['public_metrics']:
                    user['public_metrics'] = json.loads(user['public_metrics'])
            
            return users
    except Exception as e:
        logger.error(f"Error getting comprehensive users data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# END COMPREHENSIVE X API ENDPOINTS
# ============================================================================

@app.post("/api/profiles/enrich")
async def enrich_user_profiles(
    limit: int = Query(50, ge=1, le=100, description="Number of profiles to enrich"),
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Fetch and store profile data for users in relationships who don't have profile data."""
    try:
        client = get_twitter_client()
        if not client or not client.client:
            raise HTTPException(status_code=503, detail="Twitter API not available")
        
        with sqlite3.connect(service.db_path) as conn:
            # Get users who need profile enrichment (no username or very basic data)
            cursor = conn.execute("""
                SELECT DISTINCT u.id 
                FROM users u
                WHERE (u.username IS NULL OR u.username LIKE 'user_%') 
                AND (u.profile_source IS NULL OR u.profile_source = 'local')
                AND u.id IN (
                    SELECT target_user_id FROM relationships 
                    UNION 
                    SELECT source_user_id FROM relationships
                )
                LIMIT ?
            """, (limit,))
            
            user_ids = [row[0] for row in cursor.fetchall()]
            
            if not user_ids:
                return {
                    "message": "No users need profile enrichment",
                    "enriched_count": 0,
                    "total_users": 0
                }
            
            enriched_count = 0
            failed_count = 0
            
            # Fetch users in batches (Twitter API allows up to 100 users per request)
            batch_size = 100
            for i in range(0, len(user_ids), batch_size):
                batch_ids = user_ids[i:i + batch_size]
                
                try:
                    # Fetch user data from Twitter API
                    users_response = client.client.get_users(
                        ids=batch_ids,
                        user_fields=['username', 'name', 'description', 'location', 'url', 'verified', 'profile_image_url', 'public_metrics', 'created_at']
                    )
                    
                    if users_response.data:
                        for user in users_response.data:
                            try:
                                # Update user profile in database
                                c = conn.cursor()
                                c.execute("""
                                    UPDATE users SET 
                                        username = ?,
                                        display_name = ?,
                                        bio = ?,
                                        location = ?,
                                        website = ?,
                                        verified = ?,
                                        avatar_url = ?,
                                        follower_count = ?,
                                        following_count = ?,
                                        tweet_count = ?,
                                        created_at = ?,
                                        last_updated = CURRENT_TIMESTAMP,
                                        profile_source = 'api'
                                    WHERE id = ?
                                """, (
                                    user.username,
                                    user.name,
                                    user.description,
                                    user.location,
                                    user.url,
                                    user.verified or False,
                                    user.profile_image_url,
                                    user.public_metrics.get('followers_count') if user.public_metrics else None,
                                    user.public_metrics.get('following_count') if user.public_metrics else None,
                                    user.public_metrics.get('tweet_count') if user.public_metrics else None,
                                    user.created_at.isoformat() if user.created_at else None,
                                    user.id
                                ))
                                enriched_count += 1
                                
                            except Exception as e:
                                print(f"Error updating user {user.id}: {e}")
                                failed_count += 1
                        
                        conn.commit()
                        
                    # Rate limiting: sleep between batches
                    import time
                    time.sleep(1)
                    
                except tweepy.TooManyRequests:
                    return {
                        "message": f"Rate limited after enriching {enriched_count} profiles",
                        "enriched_count": enriched_count,
                        "failed_count": failed_count,
                        "total_users": len(user_ids)
                    }
                except Exception as e:
                    print(f"Error fetching batch starting at index {i}: {e}")
                    failed_count += len(batch_ids)
            
            return {
                "message": f"Successfully enriched {enriched_count} user profiles",
                "enriched_count": enriched_count,
                "failed_count": failed_count,
                "total_users": len(user_ids)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profiles/stats")
async def get_profile_stats(service: LocalTwitterService = Depends(get_local_twitter_service)):
    """Get statistics about profile data availability."""
    try:
        with sqlite3.connect(service.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN profile_source = 'api' THEN 1 END) as api_profiles,
                    COUNT(CASE WHEN profile_source = 'local' THEN 1 END) as local_profiles,
                    COUNT(CASE WHEN username IS NOT NULL AND NOT username LIKE 'user_%' THEN 1 END) as with_username,
                    COUNT(CASE WHEN avatar_url IS NOT NULL THEN 1 END) as with_avatar,
                    COUNT(CASE WHEN verified = 1 THEN 1 END) as verified_users
                FROM users
            """)
            
            stats = cursor.fetchone()
            
            # Get relationship stats
            cursor = conn.execute("""
                SELECT 
                    relationship_type,
                    COUNT(*) as count
                FROM relationships 
                GROUP BY relationship_type
            """)
            
            relationships = dict(cursor.fetchall())
            
            return {
                "users": {
                    "total": stats[0],
                    "with_api_profiles": stats[1], 
                    "with_local_profiles": stats[2],
                    "with_usernames": stats[3],
                    "with_avatars": stats[4],
                    "verified": stats[5]
                },
                "relationships": relationships
            }
            
    except Exception as e:
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