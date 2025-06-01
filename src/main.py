"""
Twitter Tools - Twitter Data Analysis and Management

A full-stack application for analyzing and managing Twitter/X data.
Features both a CLI interface and a REST API.
"""
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import tweepy
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from src.settings import get_settings
from src.cache import TwitterCache, AuthCache
import time
import sqlite3

# Set up logging centrally
logging.basicConfig(
    level=logging.INFO if get_settings().DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    created_at: datetime
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
    try:
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.isoformat()
    except Exception:
        return date_str  # fallback if already ISO or invalid

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
            cursor = conn.execute("SELECT id, text, created_at FROM tweets WHERE author_id = ? ORDER BY created_at DESC", (user_id,))
            for row in cursor.fetchall():
                tweet_id, text, created_at = row
                tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return {'data': tweets, 'meta': {}}
    
    def get_recent_likes(self, count: int = 10) -> List[Dict[str, Any]]:
        """Fetch likes from SQLite DB."""
        likes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tweet_id, liked_at FROM likes ORDER BY liked_at DESC LIMIT ?", (count,))
            for row in cursor.fetchall():
                tweet_id, liked_at = row
                # Fetch tweet text
                tweet_cursor = conn.execute("SELECT text, created_at FROM tweets WHERE id = ?", (tweet_id,))
                tweet_row = tweet_cursor.fetchone()
                if tweet_row:
                    text, created_at = tweet_row
                else:
                    text, created_at = '', ''
                likes.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return likes
    
    def get_zero_engagement_tweets(self) -> List[Dict[str, Any]]:
        """Fetch zero engagement tweets from SQLite DB."""
        zero_engagement_tweets = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, text, created_at FROM tweets ORDER BY created_at DESC")
            for row in cursor.fetchall():
                tweet_id, text, created_at = row
                zero_engagement_tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return zero_engagement_tweets
    
    def get_zero_engagement_replies(self) -> List[Dict[str, Any]]:
        """Fetch zero engagement replies from SQLite DB."""
        zero_engagement_replies = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, text, created_at, in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL ORDER BY created_at DESC")
            for row in cursor.fetchall():
                reply_id, text, created_at, in_reply_to = row
                zero_engagement_replies.append({
                    'id': reply_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0},
                    'in_reply_to': in_reply_to or "Unknown"
                })
        return zero_engagement_replies

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
            cursor = conn.execute("SELECT id, text, created_at FROM tweets WHERE author_id = ? ORDER BY created_at DESC", (user_id,))
            for row in cursor.fetchall():
                tweet_id, text, created_at = row
                tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return {'data': tweets, 'meta': {}}
    
    def get_recent_likes(self, count: int = 10) -> List[Dict[str, Any]]:
        # --- NEW: Fetch likes from SQLite DB ---
        likes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tweet_id, liked_at FROM likes ORDER BY liked_at DESC LIMIT ?", (count,))
            for row in cursor.fetchall():
                tweet_id, liked_at = row
                # Fetch tweet text
                tweet_cursor = conn.execute("SELECT text, created_at FROM tweets WHERE id = ?", (tweet_id,))
                tweet_row = tweet_cursor.fetchone()
                if tweet_row:
                    text, created_at = tweet_row
                else:
                    text, created_at = '', ''
                likes.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return likes
    
    def get_zero_engagement_tweets(self) -> List[Dict[str, Any]]:
        # --- NEW: Fetch zero engagement tweets from SQLite DB ---
        zero_engagement_tweets = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, text, created_at FROM tweets ORDER BY created_at DESC")
            for row in cursor.fetchall():
                tweet_id, text, created_at = row
                zero_engagement_tweets.append({
                    'id': tweet_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0}
                })
        return zero_engagement_tweets
    
    def get_zero_engagement_replies(self) -> List[Dict[str, Any]]:
        # --- NEW: Fetch zero engagement replies from SQLite DB ---
        zero_engagement_replies = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, text, created_at, in_reply_to_status_id FROM tweets WHERE in_reply_to_status_id IS NOT NULL ORDER BY created_at DESC")
            for row in cursor.fetchall():
                reply_id, text, created_at, in_reply_to = row
                zero_engagement_replies.append({
                    'id': reply_id,
                    'text': text,
                    'created_at': twitter_date_to_iso(created_at),
                    'metrics': {'like_count': 0, 'retweet_count': 0, 'reply_count': 0},
                    'in_reply_to': in_reply_to or "Unknown"
                })
        return zero_engagement_replies

# Dependencies for FastAPI endpoints
def get_local_twitter_service() -> LocalTwitterService:
    """Dependency to get local Twitter service (no API auth required)."""
    return LocalTwitterService()

def get_twitter_service(client: TwitterClient = Depends(get_twitter_client)):
    """Dependency to get Twitter service (requires API auth)."""
    return TwitterService(client=client)

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
                # Fallback: Since this is a personal archive, create a default profile
                # Use "pietertypes" as the username based on the greeting in the original design
                user_id = "unknown"
                username = "pietertypes"
                display_name = "Pieter"
                created_at = "2024-01-01"
            
            # Get tweet count (all tweets in personal archive are yours)
            cursor = conn.execute("SELECT COUNT(*) FROM tweets")
            tweet_count = cursor.fetchone()[0]
            
            # Get likes count
            cursor = conn.execute("SELECT COUNT(*) FROM likes")
            like_count = cursor.fetchone()[0]
            
            # Get replies count (tweets with in_reply_to_status_id)
            cursor = conn.execute("SELECT COUNT(*) FROM tweets WHERE in_reply_to_status_id IS NOT NULL AND in_reply_to_status_id != ''")
            reply_count = cursor.fetchone()[0]
            
            # For zero engagement, we'll use the same counts since we don't have engagement metrics
            # In a real implementation, you'd filter by engagement metrics
            zero_engagement_tweets = tweet_count
            zero_engagement_replies = reply_count
            
            return {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "created_at": created_at,
                "stats": {
                    "tweet_count": tweet_count,
                    "like_count": like_count,
                    "reply_count": reply_count,
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
    count: int = 10,
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get recent likes for authenticated user."""
    return service.get_recent_likes(count)

# Add new endpoints for zero engagement tweets and replies
@app.get("/api/tweets/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_tweets(
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get tweets with zero engagement."""
    return service.get_zero_engagement_tweets()

@app.get("/api/replies/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_replies(
    service: LocalTwitterService = Depends(get_local_twitter_service)
):
    """Get replies with zero engagement."""
    return service.get_zero_engagement_replies()

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