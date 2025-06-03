"""
In-Memory Tweet Cache Module

This module provides a simple in-memory cache for Twitter data using Python dictionaries.
All data is loaded from SQLite on startup and kept in memory for fast O(1) access.
"""

import sqlite3
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class InMemoryTweetCache:
    """
    Simple in-memory cache for Twitter data using Python dictionaries.
    
    Loads all tweets, likes, and related data from SQLite into memory on startup
    for fast O(1) access. Ideal for datasets up to ~50K tweets.
    """
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / 'data' / 'x_data.db'
        
        # Core data stores
        self.tweets: Dict[str, Dict[str, Any]] = {}
        self.likes: Dict[str, Dict[str, Any]] = {}
        self.blocks: Dict[str, Dict[str, Any]] = {}
        self.mutes: Dict[str, Dict[str, Any]] = {}
        self.users: Dict[str, Dict[str, Any]] = {}
        self.account: Dict[str, Any] = {}
        self.profile: Dict[str, Any] = {}
        
        # Index structures for fast lookups
        self.tweets_by_author: Dict[str, List[str]] = {}
        self.replies: Dict[str, List[str]] = {}  # tweet_id -> list of reply_ids
        self.liked_tweet_ids: set = set()
        
        # Cache metadata
        self.loaded = False
        self.load_time = None
        self.stats = {
            'tweets_count': 0,
            'likes_count': 0,
            'blocks_count': 0,
            'mutes_count': 0,
            'users_count': 0,
            'load_duration_seconds': 0
        }
    
    def load_all_data(self) -> None:
        """Load all data from SQLite into memory."""
        if self.loaded:
            logger.info("Cache already loaded, skipping reload")
            return
        
        start_time = time.time()
        logger.info("🚀 Loading all Twitter data into memory cache...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                
                # Load tweets
                self._load_tweets(conn)
                
                # Load likes
                self._load_likes(conn)
                
                # Load blocks
                self._load_blocks(conn)
                
                # Load mutes
                self._load_mutes(conn)
                
                # Load users (followers/following)
                self._load_users(conn)
                
                # Load account info
                self._load_account(conn)
                
                # Load profile info
                self._load_profile(conn)
                
                # Build indexes
                self._build_indexes()
            
            self.loaded = True
            self.load_time = time.time()
            self.stats['load_duration_seconds'] = round(self.load_time - start_time, 2)
            
            logger.info("✅ Cache loaded successfully!")
            self._log_stats()
            
        except Exception as e:
            logger.error(f"❌ Failed to load cache: {str(e)}")
            raise
    
    def _load_tweets(self, conn: sqlite3.Connection) -> None:
        """Load all tweets into memory."""
        cursor = conn.execute("""
            SELECT id, text, created_at, conversation_id, author_id, 
                   in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name,
                   favorite_count, retweet_count, lang, deleted_at
            FROM tweets
        """)
        
        for row in cursor.fetchall():
            tweet_data = {
                'id': row['id'],
                'text': row['text'],
                'created_at': row['created_at'],
                'conversation_id': row['conversation_id'],
                'author_id': row['author_id'],
                'in_reply_to_status_id': row['in_reply_to_status_id'],
                'in_reply_to_user_id': row['in_reply_to_user_id'],
                'in_reply_to_screen_name': row['in_reply_to_screen_name'],
                'favorite_count': row['favorite_count'] or 0,
                'retweet_count': row['retweet_count'] or 0,
                'lang': row['lang'],
                'deleted_at': row['deleted_at'],
                'is_reply': bool(row['in_reply_to_status_id']),
                'is_deleted': bool(row['deleted_at'])
            }
            
            self.tweets[row['id']] = tweet_data
            self.stats['tweets_count'] += 1
        
        logger.info(f"📝 Loaded {self.stats['tweets_count']} tweets")
    
    def _load_likes(self, conn: sqlite3.Connection) -> None:
        """Load all likes into memory."""
        cursor = conn.execute("""
            SELECT tweet_id, full_text, expanded_url, liked_at
            FROM likes
        """)
        
        for row in cursor.fetchall():
            like_data = {
                'tweet_id': row['tweet_id'],
                'full_text': row['full_text'],
                'expanded_url': row['expanded_url'],
                'liked_at': row['liked_at']
            }
            
            self.likes[row['tweet_id']] = like_data
            self.liked_tweet_ids.add(row['tweet_id'])
            self.stats['likes_count'] += 1
        
        logger.info(f"❤️ Loaded {self.stats['likes_count']} likes")
    
    def _load_blocks(self, conn: sqlite3.Connection) -> None:
        """Load all blocked users into memory."""
        try:
            cursor = conn.execute("SELECT user_id, user_link FROM blocks")
            
            for row in cursor.fetchall():
                block_data = {
                    'user_id': row['user_id'],
                    'user_link': row['user_link']
                }
                
                self.blocks[row['user_id']] = block_data
                self.stats['blocks_count'] += 1
            
            logger.info(f"🚫 Loaded {self.stats['blocks_count']} blocked users")
        except sqlite3.OperationalError:
            logger.info("🚫 No blocks table found, skipping")
    
    def _load_mutes(self, conn: sqlite3.Connection) -> None:
        """Load all muted users into memory."""
        try:
            cursor = conn.execute("SELECT user_id, user_link FROM mutes")
            
            for row in cursor.fetchall():
                mute_data = {
                    'user_id': row['user_id'],
                    'user_link': row['user_link']
                }
                
                self.mutes[row['user_id']] = mute_data
                self.stats['mutes_count'] += 1
            
            logger.info(f"🔇 Loaded {self.stats['mutes_count']} muted users")
        except sqlite3.OperationalError:
            logger.info("🔇 No mutes table found, skipping")
    
    def _load_users(self, conn: sqlite3.Connection) -> None:
        """Load all users (followers/following) into memory."""
        try:
            cursor = conn.execute("SELECT id, username, display_name, user_link FROM users")
            
            for row in cursor.fetchall():
                user_data = {
                    'id': row['id'],
                    'username': row['username'],
                    'display_name': row['display_name'],
                    'user_link': row['user_link']
                }
                
                self.users[row['id']] = user_data
                self.stats['users_count'] += 1
            
            logger.info(f"👥 Loaded {self.stats['users_count']} users")
        except sqlite3.OperationalError:
            logger.info("👥 No users table found, skipping")
    
    def _load_account(self, conn: sqlite3.Connection) -> None:
        """Load account information into memory."""
        try:
            cursor = conn.execute("""
                SELECT account_id, username, display_name, email, created_at, created_via
                FROM account LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                self.account = {
                    'account_id': row['account_id'],
                    'username': row['username'],
                    'display_name': row['display_name'],
                    'email': row['email'],
                    'created_at': row['created_at'],
                    'created_via': row['created_via']
                }
                logger.info(f"👤 Loaded account: @{self.account['username']}")
        except sqlite3.OperationalError:
            logger.info("👤 No account table found, skipping")
    
    def _load_profile(self, conn: sqlite3.Connection) -> None:
        """Load profile information into memory."""
        try:
            cursor = conn.execute("""
                SELECT account_id, bio, website, location, avatar_url, header_url
                FROM profile LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                self.profile = {
                    'account_id': row['account_id'],
                    'bio': row['bio'],
                    'website': row['website'],
                    'location': row['location'],
                    'avatar_url': row['avatar_url'],
                    'header_url': row['header_url']
                }
                logger.info("📋 Loaded profile information")
        except sqlite3.OperationalError:
            logger.info("📋 No profile table found, skipping")
    
    def _build_indexes(self) -> None:
        """Build index structures for fast lookups."""
        logger.info("🔍 Building search indexes...")
        
        # Build tweets by author index
        for tweet_id, tweet in self.tweets.items():
            author_id = tweet['author_id']
            if author_id not in self.tweets_by_author:
                self.tweets_by_author[author_id] = []
            self.tweets_by_author[author_id].append(tweet_id)
        
        # Build replies index
        for tweet_id, tweet in self.tweets.items():
            if tweet['in_reply_to_status_id']:
                parent_id = tweet['in_reply_to_status_id']
                if parent_id not in self.replies:
                    self.replies[parent_id] = []
                self.replies[parent_id].append(tweet_id)
        
        logger.info("✅ Indexes built successfully")
    
    def _log_stats(self) -> None:
        """Log cache statistics."""
        logger.info("📊 Cache Statistics:")
        logger.info(f"   • Tweets: {self.stats['tweets_count']:,}")
        logger.info(f"   • Likes: {self.stats['likes_count']:,}")
        logger.info(f"   • Blocks: {self.stats['blocks_count']:,}")
        logger.info(f"   • Mutes: {self.stats['mutes_count']:,}")
        logger.info(f"   • Users: {self.stats['users_count']:,}")
        logger.info(f"   • Load time: {self.stats['load_duration_seconds']}s")
    
    # === Public API Methods ===
    
    def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a tweet by ID."""
        return self.tweets.get(tweet_id)
    
    def get_tweets_by_author(self, author_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all tweets by a specific author."""
        tweet_ids = self.tweets_by_author.get(author_id, [])
        tweets = [self.tweets[tid] for tid in tweet_ids]
        
        # Sort by created_at descending
        tweets.sort(key=lambda t: t['created_at'], reverse=True)
        
        if limit:
            tweets = tweets[:limit]
        
        return tweets
    
    def get_recent_tweets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent tweets across all authors."""
        all_tweets = list(self.tweets.values())
        all_tweets.sort(key=lambda t: t['created_at'], reverse=True)
        return all_tweets[:limit]
    
    def get_replies_to_tweet(self, tweet_id: str) -> List[Dict[str, Any]]:
        """Get all replies to a specific tweet."""
        reply_ids = self.replies.get(tweet_id, [])
        return [self.tweets[rid] for rid in reply_ids if rid in self.tweets]
    
    def get_user_replies(self, author_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all replies by a specific user."""
        user_tweets = self.get_tweets_by_author(author_id)
        replies = [t for t in user_tweets if t['is_reply']]
        
        if limit:
            replies = replies[:limit]
        
        return replies
    
    def get_liked_tweets(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all liked tweets."""
        likes = list(self.likes.values())
        likes.sort(key=lambda l: l['liked_at'] or '', reverse=True)
        
        if limit:
            likes = likes[:limit]
        
        return likes
    
    def is_tweet_liked(self, tweet_id: str) -> bool:
        """Check if a tweet is liked."""
        return tweet_id in self.liked_tweet_ids
    
    def get_zero_engagement_tweets(self, author_id: str) -> List[Dict[str, Any]]:
        """Get tweets with zero engagement (0 likes, 0 retweets)."""
        user_tweets = self.get_tweets_by_author(author_id)
        return [
            t for t in user_tweets 
            if t['favorite_count'] == 0 and t['retweet_count'] == 0 and not t['is_deleted']
        ]
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        return self.account
    
    def get_profile_info(self) -> Dict[str, Any]:
        """Get profile information."""
        return self.profile
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            **self.stats,
            'loaded': self.loaded,
            'load_time': self.load_time
        }
    
    def reload(self) -> None:
        """Reload all data from SQLite."""
        logger.info("🔄 Reloading cache...")
        self.loaded = False
        self.tweets.clear()
        self.likes.clear()
        self.blocks.clear()
        self.mutes.clear()
        self.users.clear()
        self.tweets_by_author.clear()
        self.replies.clear()
        self.liked_tweet_ids.clear()
        self.account.clear()
        self.profile.clear()
        
        # Reset stats
        for key in self.stats:
            if key.endswith('_count'):
                self.stats[key] = 0
        
        self.load_all_data()


# Global cache instance
cache = InMemoryTweetCache() 