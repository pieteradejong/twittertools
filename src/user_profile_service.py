import sqlite3
import logging
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
import json
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class UserProfileService:
    """Service to enrich user profiles for tweet authors with efficient caching."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
        self.cache_ttl_days = 7  # Cache user profiles for 7 days
        self._init_profile_cache_table()
    
    def _init_profile_cache_table(self):
        """Initialize the user profile cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles_cache (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    display_name TEXT,
                    avatar_url TEXT,
                    bio TEXT,
                    verified BOOLEAN,
                    followers_count INTEGER,
                    following_count INTEGER,
                    tweet_count INTEGER,
                    created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    source TEXT  -- 'api', 'archive', 'extracted'
                )
            """)
            
            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles_cache(username)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_expires ON user_profiles_cache(expires_at)")
    
    def get_user_profile(self, user_id: Optional[str] = None, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user profile from cache or fetch if needed."""
        if not user_id and not username:
            return None
        
        # Try cache first
        profile = self._get_cached_profile(user_id, username)
        if profile and not self._is_expired(profile['expires_at']):
            return profile
        
        # Try to get from existing users table (from archive)
        archive_profile = self._get_archive_profile(user_id, username)
        if archive_profile:
            # Cache the archive profile
            self._cache_profile(archive_profile, source='archive')
            return archive_profile
        
        # If we have Twitter API credentials, fetch from API
        # For now, return None - API fetching can be added later
        logger.debug(f"No profile found for user_id={user_id}, username={username}")
        return None
    
    def _get_cached_profile(self, user_id: Optional[str], username: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get profile from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if user_id:
                cursor = conn.execute(
                    "SELECT * FROM user_profiles_cache WHERE user_id = ?", 
                    (user_id,)
                )
            elif username:
                cursor = conn.execute(
                    "SELECT * FROM user_profiles_cache WHERE username = ?", 
                    (username,)
                )
            else:
                return None
            
            row = cursor.fetchone()
            if row:
                return dict(row)
        
        return None
    
    def _get_archive_profile(self, user_id: Optional[str], username: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get profile from existing users table (from Twitter archive)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if user_id:
                cursor = conn.execute(
                    "SELECT id, username, display_name, user_link FROM users WHERE id = ?", 
                    (user_id,)
                )
            elif username:
                cursor = conn.execute(
                    "SELECT id, username, display_name, user_link FROM users WHERE username = ?", 
                    (username,)
                )
            else:
                return None
            
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row['id'],
                    'username': row['username'],
                    'display_name': row['display_name'],
                    'avatar_url': None,  # Not available in archive
                    'bio': None,
                    'verified': False,
                    'followers_count': None,
                    'following_count': None,
                    'tweet_count': None,
                    'created_at': None,
                    'source': 'archive'
                }
        
        return None
    
    def _cache_profile(self, profile: Dict[str, Any], source: str = 'api'):
        """Cache a user profile."""
        expires_at = datetime.now() + timedelta(days=self.cache_ttl_days)
        cached_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_profiles_cache 
                (user_id, username, display_name, avatar_url, bio, verified, 
                 followers_count, following_count, tweet_count, created_at, 
                 cached_at, expires_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.get('user_id'),
                profile.get('username'),
                profile.get('display_name'),
                profile.get('avatar_url'),
                profile.get('bio'),
                profile.get('verified', False),
                profile.get('followers_count'),
                profile.get('following_count'),
                profile.get('tweet_count'),
                profile.get('created_at'),
                cached_at.isoformat(),
                expires_at.isoformat(),
                source
            ))
    
    def _is_expired(self, expires_at_str: str) -> bool:
        """Check if a cached profile is expired."""
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now() > expires_at
        except:
            return True
    
    def enrich_likes_with_authors(self, likes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich a list of likes with author profile information."""
        enriched_likes = []
        
        for like in likes:
            enriched_like = like.copy()
            
            # Get author profile
            author_profile = self.get_user_profile(
                user_id=like.get('author_id'),
                username=like.get('author_username')
            )
            
            if author_profile:
                enriched_like['author'] = {
                    'id': author_profile.get('user_id'),
                    'username': author_profile.get('username'),
                    'display_name': author_profile.get('display_name'),
                    'avatar_url': author_profile.get('avatar_url'),
                    'verified': author_profile.get('verified', False)
                }
            else:
                # Fallback to basic info if available
                enriched_like['author'] = {
                    'id': like.get('author_id'),
                    'username': like.get('author_username'),
                    'display_name': like.get('author_username'),  # Fallback
                    'avatar_url': None,
                    'verified': False
                }
            
            enriched_likes.append(enriched_like)
        
        return enriched_likes
    
    def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about cached profiles."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_cached,
                    COUNT(CASE WHEN source = 'api' THEN 1 END) as from_api,
                    COUNT(CASE WHEN source = 'archive' THEN 1 END) as from_archive,
                    COUNT(CASE WHEN expires_at > datetime('now') THEN 1 END) as valid_cache
                FROM user_profiles_cache
            """)
            
            row = cursor.fetchone()
            return {
                'total_cached': row[0],
                'from_api': row[1],
                'from_archive': row[2],
                'valid_cache': row[3]
            }
    
    def cleanup_expired_profiles(self):
        """Remove expired profiles from cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM user_profiles_cache WHERE expires_at < datetime('now')"
            )
            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} expired user profiles")
            return deleted_count 