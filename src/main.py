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

from src.config import twitter_config, app_config, create_env_template

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Twitter Tools API",
    description="API for analyzing and managing Twitter/X data",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_config.frontend_url],
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

class AuthStatus(BaseModel):
    is_authenticated: bool
    username: Optional[str] = None
    error: Optional[str] = None
    can_fetch_data: bool = False
    test_tweet_count: Optional[int] = None
    rate_limit: Optional[RateLimitInfo] = None

class TwitterClient:
    """Singleton class to manage Twitter API client."""
    
    _instance = None
    _client = None
    _rate_limit_info = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TwitterClient, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance
    
    def _handle_rate_limit(self, e: tweepy.TooManyRequests) -> None:
        """Handle rate limit exceeded error."""
        reset_time = datetime.fromtimestamp(e.response.headers.get('x-rate-limit-reset', 0))
        wait_seconds = int((reset_time - datetime.now()).total_seconds())
        endpoint = e.response.url.split('/')[-1]  # Get the endpoint that was rate limited
        
        self._rate_limit_info = RateLimitInfo(
            is_rate_limited=True,
            reset_time=reset_time,
            wait_seconds=wait_seconds,
            endpoint=endpoint
        )
        
        logger.warning(f"Rate limit exceeded for {endpoint}. Reset at {reset_time}. Waiting {wait_seconds} seconds.")
    
    def _clear_rate_limit(self) -> None:
        """Clear rate limit information."""
        self._rate_limit_info = None
    
    def _initialize_client(self):
        """Initialize the Twitter client with credentials."""
        if not twitter_config.validate_credentials():
            create_env_template()
            raise ValueError("Twitter credentials not found. Please check your .env file.")
        
        try:
            # First try with just the bearer token
            logger.info("Testing authentication with Bearer Token only...")
            bearer_client = tweepy.Client(
                bearer_token=twitter_config.get_bearer_token(),
                wait_on_rate_limit=True,  # Enable built-in rate limit handling
                return_type=dict  # Return dictionaries instead of objects for better control
            )
            
            # Test bearer token
            try:
                test_tweet = bearer_client.get_tweet(123456789)  # This will fail but we just want to test auth
            except tweepy.NotFound:
                logger.info("Bearer Token authentication successful!")
            except tweepy.TooManyRequests as e:
                self._handle_rate_limit(e)
                raise
            except tweepy.Unauthorized as e:
                logger.error("Bearer Token authentication failed!")
                logger.error("Please verify your Bearer Token in the Twitter Developer Portal")
                raise
            
            # Now try with full OAuth
            logger.info("Testing full OAuth authentication...")
            self._client = tweepy.Client(
                bearer_token=twitter_config.get_bearer_token(),
                consumer_key=twitter_config.get_api_key(),
                consumer_secret=twitter_config.get_api_secret(),
                access_token=twitter_config.get_access_token(),
                access_token_secret=twitter_config.get_access_token_secret(),
                wait_on_rate_limit=True,  # Enable built-in rate limit handling
                return_type=dict  # Return dictionaries instead of objects for better control
            )
            
            # Test OAuth by getting user info
            try:
                me = self._client.get_me()
                logger.info(f"OAuth authentication successful! Authenticated as: @{me['data']['username']}")
                self._clear_rate_limit()  # Clear any rate limit info on successful auth
            except tweepy.TooManyRequests as e:
                self._handle_rate_limit(e)
                raise
            
        except tweepy.Unauthorized as e:
            logger.error("Authentication failed. Please check your credentials:")
            logger.error("1. Make sure your API keys and tokens are correct")
            logger.error("2. Verify that your Twitter Developer account is active")
            logger.error("3. Check if your app has the required permissions")
            logger.error("4. Verify your app's OAuth 2.0 settings in the Developer Portal")
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
        """Get the Twitter client instance."""
        if not self._client:
            self._initialize_client()
        return self._client

# Dependency for FastAPI endpoints
def get_twitter_client() -> TwitterClient:
    """Dependency to get Twitter client instance."""
    return TwitterClient()

class TwitterService:
    """Service class for Twitter operations."""
    
    def __init__(self, client: Optional[TwitterClient] = None):
        if client is None:
            client = TwitterClient()
        self.client = client.client
        self.console = Console()
    
    def get_recent_likes(self, count: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent likes for the authenticated user."""
        try:
            # Get user ID for the authenticated user
            me = self.client.get_me()
            user_id = me.data.id
            
            # Get recent likes
            likes = self.client.get_liked_tweets(
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
        me = service.client.get_me()
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
        # Get user ID for the authenticated user
        me = service.client.get_me()
        user_id = me.data.id
        
        # Get user's tweets
        tweets = service.client.get_users_tweets(
            user_id,
            max_results=100,  # Adjust as needed
            tweet_fields=['created_at', 'public_metrics', 'text', 'in_reply_to_user_id'],
            exclude=['retweets', 'replies']  # Only get original tweets
        )
        
        if not tweets.data:
            return []
        
        # Filter for zero engagement tweets
        zero_engagement_tweets = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            # Consider a tweet to have zero engagement if it has no likes, retweets, or replies
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
        me = service.client.get_me()
        user_id = me.data.id
        
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
    try:
        # Get rate limit info if any
        rate_limit = service.client.rate_limit_info
        
        # If we're rate limited, return that status
        if rate_limit and rate_limit.is_rate_limited:
            return AuthStatus(
                is_authenticated=True,  # We might still be authenticated
                rate_limit=rate_limit,
                error=f"Rate limited on {rate_limit.endpoint}. Reset in {rate_limit.wait_seconds} seconds."
            )
        
        # Test authentication by getting user info
        me = service.client.get_me()
        username = me['data']['username']
        
        # Test data fetching by getting a single tweet
        try:
            tweets = service.client.get_users_tweets(
                me['data']['id'],
                max_results=1,
                tweet_fields=['created_at', 'public_metrics', 'text']
            )
            
            return AuthStatus(
                is_authenticated=True,
                username=username,
                can_fetch_data=True,
                test_tweet_count=len(tweets['data']) if tweets.get('data') else 0,
                rate_limit=service.client.rate_limit_info
            )
        except tweepy.TooManyRequests as e:
            service.client._handle_rate_limit(e)
            return AuthStatus(
                is_authenticated=True,
                username=username,
                rate_limit=service.client.rate_limit_info,
                error=f"Rate limited while fetching tweets. Reset in {service.client.rate_limit_info.wait_seconds} seconds."
            )
        
    except tweepy.Unauthorized as e:
        logger.error(f"Authentication test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=False,
            error="Authentication failed. Please check your Twitter API credentials.",
            can_fetch_data=False
        )
    except tweepy.Forbidden as e:
        logger.error(f"Permission test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error="API permissions issue. Please check your app's permissions in the Twitter Developer Portal.",
            can_fetch_data=False
        )
    except tweepy.TweepyException as e:
        logger.error(f"API test failed: {str(e)}")
        return AuthStatus(
            is_authenticated=True,
            username=username if 'username' in locals() else None,
            error=f"API error: {str(e)}",
            can_fetch_data=False
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