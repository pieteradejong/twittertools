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
import time

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
    allow_origins=[settings.FRONTEND_URL],
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
    current_step: Optional[str] = None  # Current step being performed

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
            self._user_client = tweepy.Client(
                consumer_key=settings.TWITTER_API_KEY,
                consumer_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                return_type=dict
            )
            
            # Initialize App-level client (Bearer Token)
            if settings.TWITTER_BEARER_TOKEN:
                logger.info("Initializing Twitter App-level client (Bearer Token)...")
                self._app_client = tweepy.Client(
                    bearer_token=settings.TWITTER_BEARER_TOKEN,
                    return_type=dict
                )
            
            # Test User Context authentication
            try:
                me = self._user_client.get_me()
                logger.info(f"OAuth 1.0a authentication successful! Authenticated as: @{me['data']['username']}")
                self._clear_rate_limit()
            except tweepy.TooManyRequests as e:
                self._handle_rate_limit(e)
                raise
            
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
        return self._make_request(client, "tweets", "GET", f"/2/tweets/{tweet_id}")

    def get_users_tweets(self, user_id: str, use_app_auth: bool = True, **kwargs) -> dict:
        """Get user tweets using either App-level or User Context authentication."""
        client = self.app_client if use_app_auth and self.app_client else self.client
        return self._make_request(client, "users/:id/tweets", "GET", f"/2/users/{user_id}/tweets", **kwargs)

# Dependency for FastAPI endpoints
def get_twitter_client() -> TwitterClient:
    """Dependency to get Twitter client instance."""
    return TwitterClient()

class TwitterService:
    """Service class for Twitter operations."""
    
    def __init__(self, client: Optional[TwitterClient] = None):
        if client is None:
            client = TwitterClient()
        self.client = client
        self.console = Console()
    
    def get_recent_likes(self, count: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent likes for the authenticated user."""
        try:
            # Get user ID for the authenticated user (requires User Context)
            me = self.client.client.get_me()
            user_id = me['data']['id']
            
            # Get recent likes (requires User Context)
            likes = self.client.client.get_liked_tweets(
                user_id,
                max_results=count,
                tweet_fields=['created_at', 'public_metrics', 'text']
            )
            
            if not likes.data:
                logger.info("No likes found")
                return []
            
            # Format the results
            formatted_likes = []
            for tweet in likes.data:
                formatted_likes.append({
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'metrics': tweet.public_metrics
                })
            
            return formatted_likes
            
        except tweepy.Unauthorized as e:
            logger.error("Authentication failed while fetching likes:")
            logger.error("1. Your credentials might have expired")
            logger.error("2. Your app might not have the 'Likes' permission")
            logger.error(f"Error details: {str(e)}")
            raise HTTPException(status_code=401, detail=str(e))
        except tweepy.TweepyException as e:
            logger.error(f"Error fetching likes: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def display_likes(self, likes: List[Dict[str, Any]]) -> None:
        """Display likes in a formatted table using Rich."""
        if not likes:
            self.console.print("[yellow]No likes found![/yellow]")
            return
        
        table = Table(title="Recent Twitter Likes")
        table.add_column("Date", style="cyan")
        table.add_column("Tweet", style="green")
        table.add_column("Likes", justify="right", style="magenta")
        table.add_column("Retweets", justify="right", style="blue")
        
        for like in likes:
            created_at = like['created_at'].strftime("%Y-%m-%d %H:%M")
            metrics = like['metrics']
            table.add_row(
                created_at,
                like['text'][:100] + "..." if len(like['text']) > 100 else like['text'],
                str(metrics['like_count']),
                str(metrics['retweet_count'])
            )
        
        self.console.print(table)

# Dependency for FastAPI endpoints
def get_twitter_service(client: TwitterClient = Depends(get_twitter_client)):
    return TwitterService(client=client)

# FastAPI endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

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
    service: TwitterService = Depends(get_twitter_service)
):
    """Get recent likes for authenticated user."""
    return service.get_recent_likes(count)

# Add new endpoints for zero engagement tweets and replies
@app.get("/api/tweets/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_tweets(
    service: TwitterService = Depends(get_twitter_service)
):
    """Get tweets with zero engagement."""
    try:
        # Get user ID for the authenticated user (requires User Context)
        me = service.client.client.get_me()
        user_id = me['data']['id']
        
        # Get user's tweets (can use App-level auth)
        tweets = service.client.get_users_tweets(
            user_id,
            max_results=100,
            tweet_fields=['created_at', 'public_metrics', 'text', 'in_reply_to_user_id'],
            exclude=['retweets', 'replies'],
            use_app_auth=True  # Use App-level auth when possible
        )
        
        if not tweets.data:
            return []
        
        # Filter for zero engagement tweets
        zero_engagement_tweets = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            if metrics['like_count'] == 0 and metrics['retweet_count'] == 0 and metrics['reply_count'] == 0:
                zero_engagement_tweets.append({
                    'id': str(tweet.id),
                    'text': tweet.text,
                    'created_at': tweet.created_at.isoformat(),
                    'engagement_count': 0
                })
        
        return zero_engagement_tweets
        
    except tweepy.TweepyException as e:
        logger.error(f"Error fetching zero engagement tweets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/replies/zero-engagement", response_model=List[Tweet])
async def get_zero_engagement_replies(
    service: TwitterService = Depends(get_twitter_service)
):
    """Get replies with zero engagement."""
    try:
        # Get user ID for the authenticated user
        me = service.client.client.get_me()
        user_id = me['data']['id']
        
        # Get user's replies
        replies = service.client.get_users_tweets(
            user_id,
            max_results=100,  # Adjust as needed
            tweet_fields=['created_at', 'public_metrics', 'text', 'in_reply_to_user_id', 'referenced_tweets'],
            exclude=['retweets']  # Include replies but exclude retweets
        )
        
        if not replies.data:
            return []
        
        # Filter for zero engagement replies
        zero_engagement_replies = []
        for reply in replies.data:
            # Skip if not a reply
            if not reply.in_reply_to_user_id:
                continue
                
            metrics = reply.public_metrics
            # Consider a reply to have zero engagement if it has no likes, retweets, or replies
            if metrics['like_count'] == 0 and metrics['retweet_count'] == 0 and metrics['reply_count'] == 0:
                # Get the tweet this is replying to
                referenced_tweet = None
                if reply.referenced_tweets:
                    for ref in reply.referenced_tweets:
                        if ref.type == 'replied_to':
                            try:
                                original_tweet = service.client.get_tweet(ref.id)
                                referenced_tweet = original_tweet.data
                            except tweepy.TweepyException:
                                referenced_tweet = None
                            break
                
                zero_engagement_replies.append({
                    'id': str(reply.id),
                    'text': reply.text,
                    'created_at': reply.created_at.isoformat(),
                    'engagement_count': 0,
                    'in_reply_to': referenced_tweet.text if referenced_tweet else "Original tweet not found"
                })
        
        return zero_engagement_replies
        
    except tweepy.TweepyException as e:
        logger.error(f"Error fetching zero engagement replies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-auth", response_model=AuthStatus)
async def test_authentication(
    service: TwitterService = Depends(get_twitter_service)
):
    """Test Twitter API authentication and data fetching capabilities."""
    auth_steps = []
    current_step = "Initializing authentication test..."
    
    try:
        # Get rate limit info if any
        rate_limit = service.client.rate_limit_info
        
        # If we're rate limited, return that status
        if rate_limit and rate_limit.is_rate_limited:
            return AuthStatus(
                is_authenticated=True,  # We might still be authenticated
                rate_limit=rate_limit,
                error=f"Rate limited on {rate_limit.endpoint}. Reset in {rate_limit.wait_seconds} seconds.",
                auth_steps=auth_steps,
                current_step="Rate limited"
            )
        
        # Test OAuth 1.0a authentication
        current_step = "Testing OAuth 1.0a authentication..."
        try:
            me = service.client.client.get_me()
            username = me['data']['username']
            auth_steps.append(f"OAuth 1.0a authentication successful as @{username}")
            
            # Test data fetching capability
            current_step = "Testing data fetching capability..."
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
                    rate_limit=service.client.rate_limit_info,
                    auth_steps=auth_steps,
                    current_step="All authentication tests passed"
                )
            except tweepy.TooManyRequests as e:
                service.client.client._handle_rate_limit(e)
                return AuthStatus(
                    is_authenticated=True,
                    username=username,
                    rate_limit=service.client.rate_limit_info,
                    error=f"Rate limited while testing data fetching. Reset in {service.client.rate_limit_info.wait_seconds} seconds.",
                    auth_steps=auth_steps,
                    current_step="Rate limited during data fetch test"
                )
            
        except tweepy.TooManyRequests as e:
            service.client.client._handle_rate_limit(e)
            return AuthStatus(
                is_authenticated=True,
                rate_limit=service.client.rate_limit_info,
                error=f"Rate limited during OAuth test. Reset in {service.client.rate_limit_info.wait_seconds} seconds.",
                auth_steps=auth_steps,
                current_step="Rate limited during OAuth test"
            )
        except tweepy.Unauthorized:
            return AuthStatus(
                is_authenticated=False,
                error="OAuth 1.0a authentication failed. Please check your OAuth credentials.",
                auth_steps=auth_steps,
                current_step="OAuth authentication failed"
            )
        
    except tweepy.Forbidden as e:
        logger.error(f"Permission test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error="API permissions issue. Please check your app's permissions in the Twitter Developer Portal.",
            can_fetch_data=False,
            auth_steps=auth_steps,
            current_step="Permission check failed"
        )
    except tweepy.TweepyException as e:
        logger.error(f"API test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error=f"API error: {str(e)}",
            can_fetch_data=False,
            auth_steps=auth_steps,
            current_step="API error occurred"
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