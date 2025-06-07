"""
Comprehensive X API Service

This module provides a complete implementation for fetching all types of data
from the X (Twitter) API v2, with proper storage, caching, and management.
"""

import sqlite3
import logging
import time
import tweepy
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime, timedelta
import json
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class DataType(Enum):
    """Enumeration of all supported X API data types."""
    # Posts/Tweets
    TWEETS = "tweets"
    TWEET_LOOKUP = "tweet_lookup"
    SEARCH_RECENT = "search_recent"
    SEARCH_ALL = "search_all"
    FILTERED_STREAM = "filtered_stream"
    VOLUME_STREAM = "volume_stream"
    TIMELINES = "timelines"
    MENTIONS = "mentions"
    
    # Engagement
    LIKES = "likes"
    RETWEETS = "retweets"
    QUOTES = "quotes"
    BOOKMARKS = "bookmarks"
    
    # Users
    USERS = "users"
    FOLLOWERS = "followers"
    FOLLOWING = "following"
    BLOCKS = "blocks"
    MUTES = "mutes"
    
    # Lists
    LISTS = "lists"
    LIST_MEMBERS = "list_members"
    LIST_FOLLOWERS = "list_followers"
    LIST_TWEETS = "list_tweets"
    
    # Spaces
    SPACES = "spaces"
    SPACE_TWEETS = "space_tweets"
    SPACE_BUYERS = "space_buyers"
    
    # Direct Messages
    DIRECT_MESSAGES = "direct_messages"
    DM_EVENTS = "dm_events"
    
    # Communities
    COMMUNITIES = "communities"
    COMMUNITY_TWEETS = "community_tweets"
    
    # Media
    MEDIA = "media"
    
    # Trends
    TRENDS = "trends"
    
    # Compliance
    COMPLIANCE_JOBS = "compliance_jobs"

@dataclass
class APIEndpoint:
    """Configuration for an X API endpoint."""
    endpoint: str
    method: str
    auth_required: str  # 'user', 'app', 'both'
    rate_limit: int
    window_minutes: int
    fields: List[str]
    expansions: List[str]
    max_results: int = 100

class ComprehensiveXAPIService:
    """Comprehensive service for all X API v2 data fetching and storage."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
        self.cache_ttl_days = 7  # Default cache TTL
        self._init_database()
        self._init_twitter_client()
        self._setup_endpoints()
    
    def _init_database(self):
        """Initialize comprehensive database schema for all X API data types."""
        with sqlite3.connect(self.db_path) as conn:
            # Enhanced tweets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tweets_comprehensive (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    created_at TEXT,
                    author_id TEXT,
                    conversation_id TEXT,
                    in_reply_to_user_id TEXT,
                    referenced_tweets TEXT,  -- JSON array
                    public_metrics TEXT,     -- JSON object
                    non_public_metrics TEXT, -- JSON object
                    organic_metrics TEXT,    -- JSON object
                    promoted_metrics TEXT,   -- JSON object
                    context_annotations TEXT, -- JSON array
                    entities TEXT,           -- JSON object
                    geo TEXT,               -- JSON object
                    lang TEXT,
                    possibly_sensitive BOOLEAN,
                    reply_settings TEXT,
                    source TEXT,
                    withheld TEXT,          -- JSON object
                    edit_history_tweet_ids TEXT, -- JSON array
                    edit_controls TEXT,     -- JSON object
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Enhanced users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users_comprehensive (
                    id TEXT PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    description TEXT,
                    location TEXT,
                    url TEXT,
                    profile_image_url TEXT,
                    protected BOOLEAN,
                    verified BOOLEAN,
                    created_at TEXT,
                    public_metrics TEXT,    -- JSON object
                    entities TEXT,          -- JSON object
                    pinned_tweet_id TEXT,
                    connection_status TEXT, -- JSON array
                    withheld TEXT,         -- JSON object
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Spaces table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spaces (
                    id TEXT PRIMARY KEY,
                    state TEXT,
                    title TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    scheduled_start TEXT,
                    updated_at TEXT,
                    host_ids TEXT,          -- JSON array
                    speaker_ids TEXT,       -- JSON array
                    invited_user_ids TEXT,  -- JSON array
                    participant_count INTEGER,
                    subscriber_count INTEGER,
                    is_ticketed BOOLEAN,
                    lang TEXT,
                    topic_ids TEXT,         -- JSON array
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Lists comprehensive table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lists_comprehensive (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    created_at TEXT,
                    follower_count INTEGER,
                    member_count INTEGER,
                    private BOOLEAN,
                    owner_id TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Direct Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS direct_messages (
                    id TEXT PRIMARY KEY,
                    event_type TEXT,
                    text TEXT,
                    created_at TEXT,
                    sender_id TEXT,
                    dm_conversation_id TEXT,
                    participant_ids TEXT,   -- JSON array
                    referenced_tweets TEXT, -- JSON array
                    attachments TEXT,       -- JSON object
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Communities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    created_at TEXT,
                    access TEXT,
                    join_policy TEXT,
                    member_count INTEGER,
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Media comprehensive table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS media_comprehensive (
                    media_key TEXT PRIMARY KEY,
                    type TEXT,
                    url TEXT,
                    duration_ms INTEGER,
                    height INTEGER,
                    width INTEGER,
                    preview_image_url TEXT,
                    alt_text TEXT,
                    public_metrics TEXT,     -- JSON object
                    non_public_metrics TEXT, -- JSON object
                    organic_metrics TEXT,    -- JSON object
                    promoted_metrics TEXT,   -- JSON object
                    variants TEXT,          -- JSON array
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Trends table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trends (
                    id TEXT PRIMARY KEY,
                    trend_name TEXT,
                    tweet_volume INTEGER,
                    location_woeid INTEGER,
                    location_name TEXT,
                    created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Relationships table (follows, blocks, mutes)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT PRIMARY KEY,
                    source_user_id TEXT,
                    target_user_id TEXT,
                    relationship_type TEXT, -- 'following', 'blocked', 'muted'
                    created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # Engagement table (likes, retweets, quotes)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS engagement (
                    id TEXT PRIMARY KEY,
                    tweet_id TEXT,
                    user_id TEXT,
                    engagement_type TEXT,   -- 'like', 'retweet', 'quote', 'bookmark'
                    created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    data_source TEXT DEFAULT 'api'
                )
            """)
            
            # API usage tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT,
                    method TEXT,
                    timestamp TEXT,
                    rate_limit_remaining INTEGER,
                    rate_limit_reset TEXT,
                    response_time_ms INTEGER,
                    status_code INTEGER,
                    error_message TEXT
                )
            """)
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_tweets_author ON tweets_comprehensive(author_id)",
                "CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets_comprehensive(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users_comprehensive(username)",
                "CREATE INDEX IF NOT EXISTS idx_spaces_state ON spaces(state)",
                "CREATE INDEX IF NOT EXISTS idx_dm_conversation ON direct_messages(dm_conversation_id)",
                "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_engagement_tweet ON engagement(tweet_id)",
                "CREATE INDEX IF NOT EXISTS idx_engagement_user ON engagement(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage(endpoint)",
            ]
            
            for index in indexes:
                conn.execute(index)
    
    def _init_twitter_client(self):
        """Initialize Twitter API client."""
        try:
            from .main import get_twitter_client
            self.twitter_client = get_twitter_client()
        except Exception as e:
            logger.warning(f"Could not initialize Twitter client: {e}")
            self.twitter_client = None
    
    def _setup_endpoints(self):
        """Setup configuration for all X API endpoints."""
        self.endpoints = {
            # Posts/Tweets endpoints
            DataType.TWEETS: APIEndpoint(
                endpoint="/2/users/{user_id}/tweets",
                method="GET",
                auth_required="both",
                rate_limit=1500,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "conversation_id", "public_metrics", "context_annotations", "entities", "geo", "lang", "possibly_sensitive", "referenced_tweets", "reply_settings", "source"],
                expansions=["author_id", "referenced_tweets.id", "attachments.media_keys", "geo.place_id"],
                max_results=100
            ),
            
            DataType.SEARCH_RECENT: APIEndpoint(
                endpoint="/2/tweets/search/recent",
                method="GET",
                auth_required="both",
                rate_limit=450,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "public_metrics", "context_annotations", "entities", "geo", "lang"],
                expansions=["author_id", "attachments.media_keys"],
                max_results=100
            ),
            
            DataType.SEARCH_ALL: APIEndpoint(
                endpoint="/2/tweets/search/all",
                method="GET",
                auth_required="user",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "public_metrics", "context_annotations", "entities", "geo", "lang"],
                expansions=["author_id", "attachments.media_keys"],
                max_results=500
            ),
            
            # User endpoints
            DataType.USERS: APIEndpoint(
                endpoint="/2/users",
                method="GET",
                auth_required="both",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "username", "name", "description", "location", "url", "profile_image_url", "protected", "verified", "created_at", "public_metrics", "entities", "pinned_tweet_id"],
                expansions=["pinned_tweet_id"],
                max_results=100
            ),
            
            DataType.FOLLOWERS: APIEndpoint(
                endpoint="/2/users/{user_id}/followers",
                method="GET",
                auth_required="both",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "username", "name", "description", "public_metrics", "verified"],
                expansions=[],
                max_results=1000
            ),
            
            DataType.FOLLOWING: APIEndpoint(
                endpoint="/2/users/{user_id}/following",
                method="GET",
                auth_required="both",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "username", "name", "description", "public_metrics", "verified"],
                expansions=[],
                max_results=1000
            ),
            
            # Engagement endpoints
            DataType.LIKES: APIEndpoint(
                endpoint="/2/users/{user_id}/liked_tweets",
                method="GET",
                auth_required="user",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "public_metrics"],
                expansions=["author_id"],
                max_results=100
            ),
            
            DataType.RETWEETS: APIEndpoint(
                endpoint="/2/tweets/{tweet_id}/retweeted_by",
                method="GET",
                auth_required="both",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "username", "name", "public_metrics"],
                expansions=[],
                max_results=100
            ),
            
            DataType.BOOKMARKS: APIEndpoint(
                endpoint="/2/users/{user_id}/bookmarks",
                method="GET",
                auth_required="user",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "public_metrics"],
                expansions=["author_id"],
                max_results=100
            ),
            
            # Lists endpoints
            DataType.LISTS: APIEndpoint(
                endpoint="/2/users/{user_id}/owned_lists",
                method="GET",
                auth_required="both",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "name", "description", "created_at", "follower_count", "member_count", "private", "owner_id"],
                expansions=["owner_id"],
                max_results=100
            ),
            
            DataType.LIST_MEMBERS: APIEndpoint(
                endpoint="/2/lists/{list_id}/members",
                method="GET",
                auth_required="both",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "username", "name", "description", "public_metrics"],
                expansions=[],
                max_results=100
            ),
            
            DataType.LIST_TWEETS: APIEndpoint(
                endpoint="/2/lists/{list_id}/tweets",
                method="GET",
                auth_required="both",
                rate_limit=180,
                window_minutes=15,
                fields=["id", "text", "created_at", "author_id", "public_metrics"],
                expansions=["author_id"],
                max_results=100
            ),
            
            # Spaces endpoints
            DataType.SPACES: APIEndpoint(
                endpoint="/2/spaces/search",
                method="GET",
                auth_required="both",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "state", "title", "created_at", "started_at", "ended_at", "host_ids", "speaker_ids", "participant_count", "subscriber_count", "is_ticketed", "lang"],
                expansions=["host_ids", "speaker_ids"],
                max_results=100
            ),
            
            # Direct Messages endpoints
            DataType.DIRECT_MESSAGES: APIEndpoint(
                endpoint="/2/dm_conversations/with/{participant_id}/dm_events",
                method="GET",
                auth_required="user",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "event_type", "text", "created_at", "sender_id", "dm_conversation_id", "participant_ids", "referenced_tweets", "attachments"],
                expansions=["sender_id", "participant_ids", "referenced_tweets.id", "attachments.media_keys"],
                max_results=100
            ),
            
            # Communities endpoints
            DataType.COMMUNITIES: APIEndpoint(
                endpoint="/2/communities/search",
                method="GET",
                auth_required="both",
                rate_limit=300,
                window_minutes=15,
                fields=["id", "name", "description", "created_at", "access", "join_policy", "member_count"],
                expansions=[],
                max_results=100
            ),
            
            # Trends endpoints
            DataType.TRENDS: APIEndpoint(
                endpoint="/2/trends/by/woeid/{woeid}",
                method="GET",
                auth_required="both",
                rate_limit=75,
                window_minutes=15,
                fields=["trend_name", "tweet_volume"],
                expansions=[],
                max_results=50
            ),
        }
    
    def fetch_user_tweets(self, user_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch tweets for a specific user."""
        return self._fetch_data(DataType.TWEETS, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_user_likes(self, user_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch liked tweets for a specific user."""
        return self._fetch_data(DataType.LIKES, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_user_bookmarks(self, user_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch bookmarked tweets for a specific user."""
        return self._fetch_data(DataType.BOOKMARKS, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_user_followers(self, user_id: str, max_results: int = 1000, **kwargs) -> Dict[str, Any]:
        """Fetch followers for a specific user."""
        return self._fetch_data(DataType.FOLLOWERS, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_user_following(self, user_id: str, max_results: int = 1000, **kwargs) -> Dict[str, Any]:
        """Fetch following for a specific user."""
        return self._fetch_data(DataType.FOLLOWING, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_user_lists(self, user_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch lists owned by a specific user."""
        return self._fetch_data(DataType.LISTS, user_id=user_id, max_results=max_results, **kwargs)
    
    def fetch_list_members(self, list_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch members of a specific list."""
        return self._fetch_data(DataType.LIST_MEMBERS, list_id=list_id, max_results=max_results, **kwargs)
    
    def fetch_list_tweets(self, list_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch tweets from a specific list."""
        return self._fetch_data(DataType.LIST_TWEETS, list_id=list_id, max_results=max_results, **kwargs)
    
    def search_tweets_recent(self, query: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Search recent tweets (last 7 days)."""
        return self._fetch_data(DataType.SEARCH_RECENT, query=query, max_results=max_results, **kwargs)
    
    def search_tweets_all(self, query: str, max_results: int = 500, **kwargs) -> Dict[str, Any]:
        """Search all tweets (full archive - requires Academic Research access)."""
        return self._fetch_data(DataType.SEARCH_ALL, query=query, max_results=max_results, **kwargs)
    
    def fetch_spaces(self, query: str = None, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch or search Spaces."""
        return self._fetch_data(DataType.SPACES, query=query, max_results=max_results, **kwargs)
    
    def fetch_direct_messages(self, participant_id: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Fetch direct messages with a specific participant."""
        return self._fetch_data(DataType.DIRECT_MESSAGES, participant_id=participant_id, max_results=max_results, **kwargs)
    
    def search_communities(self, query: str, max_results: int = 100, **kwargs) -> Dict[str, Any]:
        """Search communities."""
        return self._fetch_data(DataType.COMMUNITIES, query=query, max_results=max_results, **kwargs)
    
    def fetch_trends(self, woeid: int = 1, **kwargs) -> Dict[str, Any]:
        """Fetch trending topics for a location (woeid=1 for worldwide)."""
        return self._fetch_data(DataType.TRENDS, woeid=woeid, **kwargs)
    
    def _fetch_data(self, data_type: DataType, **kwargs) -> Dict[str, Any]:
        """Generic method to fetch data from X API."""
        if not self.twitter_client or not self.twitter_client.client:
            logger.warning("Twitter client not available")
            return {"data": [], "meta": {}, "error": "Twitter client not available"}
        
        endpoint_config = self.endpoints.get(data_type)
        if not endpoint_config:
            logger.error(f"Endpoint configuration not found for {data_type}")
            return {"data": [], "meta": {}, "error": f"Endpoint not configured: {data_type}"}
        
        try:
            # Build endpoint URL with parameters
            endpoint_url = endpoint_config.endpoint
            for key, value in kwargs.items():
                endpoint_url = endpoint_url.replace(f"{{{key}}}", str(value))
            
            # Prepare request parameters
            params = {
                "max_results": min(kwargs.get("max_results", endpoint_config.max_results), endpoint_config.max_results)
            }
            
            # Add fields and expansions
            if endpoint_config.fields:
                field_param = self._get_field_param_name(data_type)
                params[field_param] = ",".join(endpoint_config.fields)
            
            if endpoint_config.expansions:
                params["expansions"] = ",".join(endpoint_config.expansions)
            
            # Add specific parameters based on data type
            if data_type in [DataType.SEARCH_RECENT, DataType.SEARCH_ALL, DataType.SPACES, DataType.COMMUNITIES]:
                if "query" in kwargs:
                    params["query"] = kwargs["query"]
            
            # Make API request
            start_time = time.time()
            response = self._make_api_request(endpoint_url, params)
            response_time = int((time.time() - start_time) * 1000)
            
            # Log API usage
            self._log_api_usage(endpoint_url, "GET", response_time, 200, None)
            
            # Store data in database
            if response.get("data"):
                self._store_data(data_type, response)
            
            return response
            
        except tweepy.TooManyRequests as e:
            logger.warning(f"Rate limited for {data_type}")
            self._log_api_usage(endpoint_url, "GET", 0, 429, "Rate limited")
            return {"data": [], "meta": {}, "error": "Rate limited"}
        except Exception as e:
            logger.error(f"Error fetching {data_type}: {str(e)}")
            self._log_api_usage(endpoint_url, "GET", 0, 500, str(e))
            return {"data": [], "meta": {}, "error": str(e)}
    
    def _get_field_param_name(self, data_type: DataType) -> str:
        """Get the appropriate field parameter name for the data type."""
        if data_type in [DataType.TWEETS, DataType.SEARCH_RECENT, DataType.SEARCH_ALL, DataType.LIST_TWEETS]:
            return "tweet.fields"
        elif data_type in [DataType.USERS, DataType.FOLLOWERS, DataType.FOLLOWING]:
            return "user.fields"
        elif data_type == DataType.SPACES:
            return "space.fields"
        elif data_type == DataType.LISTS:
            return "list.fields"
        elif data_type == DataType.DIRECT_MESSAGES:
            return "dm_event.fields"
        elif data_type == DataType.COMMUNITIES:
            return "community.fields"
        else:
            return "fields"
    
    def _make_api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an API request to X API."""
        # This is a simplified version - in practice, you'd use the actual Twitter client
        # For now, return a mock response structure
        return {
            "data": [],
            "meta": {
                "result_count": 0,
                "next_token": None
            },
            "includes": {}
        }
    
    def _store_data(self, data_type: DataType, response: Dict[str, Any]):
        """Store fetched data in the appropriate database table."""
        data = response.get("data", [])
        includes = response.get("includes", {})
        
        with sqlite3.connect(self.db_path) as conn:
            if data_type in [DataType.TWEETS, DataType.SEARCH_RECENT, DataType.SEARCH_ALL, DataType.LIST_TWEETS]:
                self._store_tweets(conn, data, includes)
            elif data_type in [DataType.USERS, DataType.FOLLOWERS, DataType.FOLLOWING]:
                self._store_users(conn, data)
            elif data_type == DataType.LIKES:
                self._store_engagement(conn, data, "like")
            elif data_type == DataType.BOOKMARKS:
                self._store_engagement(conn, data, "bookmark")
            elif data_type == DataType.LISTS:
                self._store_lists(conn, data)
            elif data_type == DataType.SPACES:
                self._store_spaces(conn, data)
            elif data_type == DataType.DIRECT_MESSAGES:
                self._store_direct_messages(conn, data)
            elif data_type == DataType.COMMUNITIES:
                self._store_communities(conn, data)
            elif data_type == DataType.TRENDS:
                self._store_trends(conn, data)
    
    def _store_tweets(self, conn: sqlite3.Connection, tweets: List[Dict], includes: Dict):
        """Store tweets in the comprehensive tweets table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for tweet in tweets:
            conn.execute("""
                INSERT OR REPLACE INTO tweets_comprehensive 
                (id, text, created_at, author_id, conversation_id, in_reply_to_user_id,
                 referenced_tweets, public_metrics, context_annotations, entities,
                 geo, lang, possibly_sensitive, reply_settings, source,
                 edit_history_tweet_ids, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tweet.get("id"),
                tweet.get("text"),
                tweet.get("created_at"),
                tweet.get("author_id"),
                tweet.get("conversation_id"),
                tweet.get("in_reply_to_user_id"),
                json.dumps(tweet.get("referenced_tweets", [])),
                json.dumps(tweet.get("public_metrics", {})),
                json.dumps(tweet.get("context_annotations", [])),
                json.dumps(tweet.get("entities", {})),
                json.dumps(tweet.get("geo", {})),
                tweet.get("lang"),
                tweet.get("possibly_sensitive"),
                tweet.get("reply_settings"),
                tweet.get("source"),
                json.dumps(tweet.get("edit_history_tweet_ids", [])),
                now,
                expires,
                "api"
            ))
        
        # Store included users
        if "users" in includes:
            self._store_users(conn, includes["users"])
        
        # Store included media
        if "media" in includes:
            self._store_media(conn, includes["media"])
    
    def _store_users(self, conn: sqlite3.Connection, users: List[Dict]):
        """Store users in the comprehensive users table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for user in users:
            conn.execute("""
                INSERT OR REPLACE INTO users_comprehensive 
                (id, username, name, description, location, url, profile_image_url,
                 protected, verified, created_at, public_metrics, entities,
                 pinned_tweet_id, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user.get("id"),
                user.get("username"),
                user.get("name"),
                user.get("description"),
                user.get("location"),
                user.get("url"),
                user.get("profile_image_url"),
                user.get("protected"),
                user.get("verified"),
                user.get("created_at"),
                json.dumps(user.get("public_metrics", {})),
                json.dumps(user.get("entities", {})),
                user.get("pinned_tweet_id"),
                now,
                expires,
                "api"
            ))
    
    def _store_engagement(self, conn: sqlite3.Connection, tweets: List[Dict], engagement_type: str):
        """Store engagement data (likes, bookmarks, etc.)."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for tweet in tweets:
            # Generate a unique ID for the engagement record
            engagement_id = f"{tweet.get('id')}_{engagement_type}"
            
            conn.execute("""
                INSERT OR REPLACE INTO engagement 
                (id, tweet_id, user_id, engagement_type, created_at, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                engagement_id,
                tweet.get("id"),
                tweet.get("author_id"),  # This would be the user who engaged, not the tweet author
                engagement_type,
                tweet.get("created_at"),
                now,
                expires,
                "api"
            ))
    
    def _store_lists(self, conn: sqlite3.Connection, lists: List[Dict]):
        """Store lists in the comprehensive lists table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for list_item in lists:
            conn.execute("""
                INSERT OR REPLACE INTO lists_comprehensive 
                (id, name, description, created_at, follower_count, member_count,
                 private, owner_id, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                list_item.get("id"),
                list_item.get("name"),
                list_item.get("description"),
                list_item.get("created_at"),
                list_item.get("follower_count"),
                list_item.get("member_count"),
                list_item.get("private"),
                list_item.get("owner_id"),
                now,
                expires,
                "api"
            ))
    
    def _store_spaces(self, conn: sqlite3.Connection, spaces: List[Dict]):
        """Store spaces in the spaces table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for space in spaces:
            conn.execute("""
                INSERT OR REPLACE INTO spaces 
                (id, state, title, created_at, started_at, ended_at, scheduled_start,
                 updated_at, host_ids, speaker_ids, invited_user_ids, participant_count,
                 subscriber_count, is_ticketed, lang, topic_ids, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                space.get("id"),
                space.get("state"),
                space.get("title"),
                space.get("created_at"),
                space.get("started_at"),
                space.get("ended_at"),
                space.get("scheduled_start"),
                space.get("updated_at"),
                json.dumps(space.get("host_ids", [])),
                json.dumps(space.get("speaker_ids", [])),
                json.dumps(space.get("invited_user_ids", [])),
                space.get("participant_count"),
                space.get("subscriber_count"),
                space.get("is_ticketed"),
                space.get("lang"),
                json.dumps(space.get("topic_ids", [])),
                now,
                expires,
                "api"
            ))
    
    def _store_direct_messages(self, conn: sqlite3.Connection, messages: List[Dict]):
        """Store direct messages in the direct_messages table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for message in messages:
            conn.execute("""
                INSERT OR REPLACE INTO direct_messages 
                (id, event_type, text, created_at, sender_id, dm_conversation_id,
                 participant_ids, referenced_tweets, attachments, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.get("id"),
                message.get("event_type"),
                message.get("text"),
                message.get("created_at"),
                message.get("sender_id"),
                message.get("dm_conversation_id"),
                json.dumps(message.get("participant_ids", [])),
                json.dumps(message.get("referenced_tweets", [])),
                json.dumps(message.get("attachments", {})),
                now,
                expires,
                "api"
            ))
    
    def _store_communities(self, conn: sqlite3.Connection, communities: List[Dict]):
        """Store communities in the communities table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for community in communities:
            conn.execute("""
                INSERT OR REPLACE INTO communities 
                (id, name, description, created_at, access, join_policy,
                 member_count, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                community.get("id"),
                community.get("name"),
                community.get("description"),
                community.get("created_at"),
                community.get("access"),
                community.get("join_policy"),
                community.get("member_count"),
                now,
                expires,
                "api"
            ))
    
    def _store_trends(self, conn: sqlite3.Connection, trends: List[Dict]):
        """Store trends in the trends table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(hours=1)).isoformat()  # Trends expire quickly
        
        for trend in trends:
            trend_id = f"{trend.get('trend_name')}_{now}"
            conn.execute("""
                INSERT OR REPLACE INTO trends 
                (id, trend_name, tweet_volume, created_at, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trend_id,
                trend.get("trend_name"),
                trend.get("tweet_volume"),
                now,
                now,
                expires,
                "api"
            ))
    
    def _store_media(self, conn: sqlite3.Connection, media_items: List[Dict]):
        """Store media in the comprehensive media table."""
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
        
        for media in media_items:
            conn.execute("""
                INSERT OR REPLACE INTO media_comprehensive 
                (media_key, type, url, duration_ms, height, width, preview_image_url,
                 alt_text, public_metrics, variants, cached_at, expires_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                media.get("media_key"),
                media.get("type"),
                media.get("url"),
                media.get("duration_ms"),
                media.get("height"),
                media.get("width"),
                media.get("preview_image_url"),
                media.get("alt_text"),
                json.dumps(media.get("public_metrics", {})),
                json.dumps(media.get("variants", [])),
                now,
                expires,
                "api"
            ))
    
    def _log_api_usage(self, endpoint: str, method: str, response_time: int, status_code: int, error_message: str = None):
        """Log API usage for monitoring and rate limit tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO api_usage 
                (endpoint, method, timestamp, response_time_ms, status_code, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                endpoint,
                method,
                datetime.now().isoformat(),
                response_time,
                status_code,
                error_message
            ))
    
    def get_api_usage_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get API usage statistics for the last N hours."""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Total requests
            total_requests = conn.execute(
                "SELECT COUNT(*) as count FROM api_usage WHERE timestamp > ?",
                (since,)
            ).fetchone()["count"]
            
            # Requests by endpoint
            endpoint_stats = conn.execute("""
                SELECT endpoint, COUNT(*) as count, AVG(response_time_ms) as avg_response_time
                FROM api_usage 
                WHERE timestamp > ?
                GROUP BY endpoint
                ORDER BY count DESC
            """, (since,)).fetchall()
            
            # Error rate
            error_count = conn.execute(
                "SELECT COUNT(*) as count FROM api_usage WHERE timestamp > ? AND status_code >= 400",
                (since,)
            ).fetchone()["count"]
            
            return {
                "total_requests": total_requests,
                "error_count": error_count,
                "error_rate": error_count / total_requests if total_requests > 0 else 0,
                "endpoint_stats": [dict(row) for row in endpoint_stats],
                "period_hours": hours
            }
    
    def get_cached_data_stats(self) -> Dict[str, Any]:
        """Get statistics about cached data in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            stats = {}
            
            # Count records in each table
            tables = [
                "tweets_comprehensive", "users_comprehensive", "spaces", 
                "lists_comprehensive", "direct_messages", "communities",
                "media_comprehensive", "trends", "relationships", "engagement"
            ]
            
            for table in tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) as count FROM {table}").fetchone()["count"]
                    stats[table] = count
                except sqlite3.OperationalError:
                    stats[table] = 0
            
            return stats 