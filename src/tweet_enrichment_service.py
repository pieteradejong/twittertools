import sqlite3
import logging
import time
import tweepy
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

class TweetEnrichmentService:
    """Service to enrich tweets with author information from Twitter API."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
        self.cache_ttl_days = 30  # Cache tweet data for 30 days
        self._init_tweet_cache_table()
        self._init_twitter_client()
    
    def _init_tweet_cache_table(self):
        """Initialize the tweet enrichment cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tweet_enrichment_cache (
                    tweet_id TEXT PRIMARY KEY,
                    author_id TEXT,
                    author_username TEXT,
                    author_display_name TEXT,
                    author_avatar_url TEXT,
                    author_verified BOOLEAN,
                    tweet_created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    source TEXT  -- 'api', 'manual'
                )
            """)
            
            # Create indexes for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tweet_enrichment_expires ON tweet_enrichment_cache(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tweet_enrichment_author ON tweet_enrichment_cache(author_username)")
    
    def _init_twitter_client(self):
        """Initialize Twitter API client if credentials are available."""
        self.client = None
        try:
            # Try to get Twitter API credentials from environment
            bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if bearer_token:
                self.client = tweepy.Client(bearer_token=bearer_token)
                logger.info("Twitter API client initialized with Bearer Token")
            elif all([api_key, api_secret, access_token, access_token_secret]):
                self.client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_token_secret
                )
                logger.info("Twitter API client initialized with OAuth 1.0a")
            else:
                logger.warning("No Twitter API credentials found. Tweet enrichment will use cached data only.")
        except Exception as e:
            logger.warning(f"Failed to initialize Twitter API client: {str(e)}")
    
    def get_tweet_details(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet details from cache or fetch from API."""
        # Try cache first
        cached_tweet = self._get_cached_tweet(tweet_id)
        if cached_tweet and not self._is_expired(cached_tweet['expires_at']):
            return cached_tweet
        
        # Try to fetch from API if available
        if self.client:
            try:
                tweet_data = self._fetch_tweet_from_api(tweet_id)
                if tweet_data:
                    self._cache_tweet(tweet_data)
                    return tweet_data
            except Exception as e:
                logger.warning(f"Failed to fetch tweet {tweet_id} from API: {str(e)}")
        
        # Return cached data even if expired, or None
        return cached_tweet
    
    def _get_cached_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tweet_enrichment_cache WHERE tweet_id = ?", 
                (tweet_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def _fetch_tweet_from_api(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tweet details from Twitter API."""
        try:
            tweet = self.client.get_tweet(
                tweet_id,
                expansions=['author_id'],
                user_fields=['username', 'name', 'profile_image_url', 'verified'],
                tweet_fields=['created_at']
            )
            
            if tweet.data and tweet.includes and 'users' in tweet.includes:
                tweet_data = tweet.data
                author = tweet.includes['users'][0]  # First user is the author
                
                return {
                    'tweet_id': tweet_id,
                    'author_id': author.id,
                    'author_username': author.username,
                    'author_display_name': author.name,
                    'author_avatar_url': author.profile_image_url,
                    'author_verified': author.verified or False,
                    'tweet_created_at': tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                    'source': 'api'
                }
        except tweepy.NotFound:
            logger.warning(f"Tweet {tweet_id} not found (may be deleted)")
        except tweepy.Unauthorized:
            logger.warning(f"Unauthorized to access tweet {tweet_id} (may be private)")
        except Exception as e:
            logger.error(f"Error fetching tweet {tweet_id}: {str(e)}")
        
        return None
    
    def _cache_tweet(self, tweet_data: Dict[str, Any]):
        """Cache tweet data."""
        expires_at = datetime.now() + timedelta(days=self.cache_ttl_days)
        cached_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tweet_enrichment_cache 
                (tweet_id, author_id, author_username, author_display_name, 
                 author_avatar_url, author_verified, tweet_created_at, 
                 cached_at, expires_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tweet_data['tweet_id'],
                tweet_data['author_id'],
                tweet_data['author_username'],
                tweet_data['author_display_name'],
                tweet_data['author_avatar_url'],
                tweet_data['author_verified'],
                tweet_data['tweet_created_at'],
                cached_at.isoformat(),
                expires_at.isoformat(),
                tweet_data['source']
            ))
    
    def _is_expired(self, expires_at_str: str) -> bool:
        """Check if cached data is expired."""
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now() > expires_at
        except:
            return True
    
    def _get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT account_id, username, display_name 
                FROM account 
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['account_id'],
                    'username': row['username'],
                    'display_name': row['display_name']
                }
        return None

    def _is_user_tweet(self, tweet_id: str) -> bool:
        """Check if a tweet belongs to the authenticated user."""
        account_info = self._get_account_info()
        if not account_info:
            return False
        
        # Check if the tweet is in the user's tweets table
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 1 FROM tweets 
                WHERE id = ? AND author_id = ?
                LIMIT 1
            """, (tweet_id, account_info['id']))
            return cursor.fetchone() is not None

    def enrich_likes_batch(self, likes: List[Dict[str, Any]], batch_size: int = 100) -> List[Dict[str, Any]]:
        """Enrich a batch of likes with author information."""
        enriched_likes = []
        account_info = self._get_account_info()  # Get account info once
        
        for i, like in enumerate(likes):
            tweet_id = like.get('id')
            if not tweet_id:
                enriched_likes.append(like)
                continue
            
            # Get tweet details
            tweet_details = self.get_tweet_details(tweet_id)
            
            enriched_like = like.copy()
            if tweet_details:
                enriched_like['author'] = {
                    'id': tweet_details.get('author_id'),
                    'username': tweet_details.get('author_username'),
                    'display_name': tweet_details.get('author_display_name'),
                    'avatar_url': tweet_details.get('author_avatar_url'),
                    'verified': tweet_details.get('author_verified', False)
                }
                # Update the like record with author info
                enriched_like['author_id'] = tweet_details.get('author_id')
                enriched_like['author_username'] = tweet_details.get('author_username')
            else:
                # Check if this is the user's own tweet
                if account_info and self._is_user_tweet(tweet_id):
                    enriched_like['author'] = {
                        'id': account_info['id'],
                        'username': account_info['username'],
                        'display_name': account_info['display_name'],
                        'avatar_url': None,
                        'verified': False
                    }
                    enriched_like['author_id'] = account_info['id']
                    enriched_like['author_username'] = account_info['username']
                else:
                    # Fallback to basic info
                    enriched_like['author'] = {
                        'id': like.get('author_id'),
                        'username': like.get('author_username'),
                        'display_name': like.get('author_username') or 'Unknown User',
                        'avatar_url': None,
                        'verified': False
                    }
            
            enriched_likes.append(enriched_like)
            
            # Rate limiting: pause between API calls
            if self.client and tweet_details and tweet_details.get('source') == 'api':
                if (i + 1) % 10 == 0:  # Pause every 10 API calls
                    time.sleep(1)
        
        return enriched_likes
    
    def update_likes_table_with_enrichment(self):
        """Update the likes table with enriched author information from cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE likes 
                SET author_id = (
                    SELECT author_id FROM tweet_enrichment_cache 
                    WHERE tweet_enrichment_cache.tweet_id = likes.tweet_id
                ),
                author_username = (
                    SELECT author_username FROM tweet_enrichment_cache 
                    WHERE tweet_enrichment_cache.tweet_id = likes.tweet_id
                )
                WHERE EXISTS (
                    SELECT 1 FROM tweet_enrichment_cache 
                    WHERE tweet_enrichment_cache.tweet_id = likes.tweet_id
                )
            """)
            
            updated_count = cursor.rowcount
            conn.commit()
            logger.info(f"Updated {updated_count} likes with enriched author information")
            return updated_count
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get statistics about tweet enrichment."""
        with sqlite3.connect(self.db_path) as conn:
            # Total likes
            cursor = conn.execute("SELECT COUNT(*) FROM likes")
            total_likes = cursor.fetchone()[0]
            
            # Likes with author info
            cursor = conn.execute("SELECT COUNT(*) FROM likes WHERE author_username IS NOT NULL")
            likes_with_authors = cursor.fetchone()[0]
            
            # Cached tweets
            cursor = conn.execute("SELECT COUNT(*) FROM tweet_enrichment_cache")
            cached_tweets = cursor.fetchone()[0]
            
            # API vs manual cache
            cursor = conn.execute("""
                SELECT 
                    COUNT(CASE WHEN source = 'api' THEN 1 END) as from_api,
                    COUNT(CASE WHEN source = 'manual' THEN 1 END) as from_manual
                FROM tweet_enrichment_cache
            """)
            row = cursor.fetchone()
            
            return {
                'total_likes': total_likes,
                'likes_with_authors': likes_with_authors,
                'coverage_percentage': (likes_with_authors / total_likes * 100) if total_likes > 0 else 0,
                'cached_tweets': cached_tweets,
                'from_api': row[0] if row else 0,
                'from_manual': row[1] if row else 0,
                'api_available': self.client is not None
            } 