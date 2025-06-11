import sqlite3
import logging
import time
import tweepy
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import json
from .config import (
    LIST_ENRICHMENT_DEFAULT_DELAY, LIST_ENRICHMENT_CACHE_TTL_DAYS,
    DATABASE_PATH
)

logger = logging.getLogger(__name__)

class ListEnrichmentService:
    """Service to enrich lists with metadata from Twitter API."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = Path(db_path)
        self.cache_ttl_days = LIST_ENRICHMENT_CACHE_TTL_DAYS  # Cache list metadata for configured days
        self._init_list_metadata_table()
        self._init_twitter_client()
    
    def _init_list_metadata_table(self):
        """Initialize the list metadata cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS list_metadata_cache (
                    list_id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    member_count INTEGER,
                    follower_count INTEGER,
                    private BOOLEAN,
                    owner_id TEXT,
                    created_at TEXT,
                    cached_at TEXT,
                    expires_at TEXT,
                    source TEXT DEFAULT 'api'
                )
            """)
            
            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_list_metadata_expires ON list_metadata_cache(expires_at)")
    
    def _init_twitter_client(self):
        """Initialize Twitter API client."""
        try:
            from .main import get_twitter_client
            self.twitter_client = get_twitter_client()
        except Exception as e:
            logger.warning(f"Could not initialize Twitter client: {e}")
            self.twitter_client = None
    
    def _cleanup_expired_cache(self):
        """Remove expired entries from the cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM list_metadata_cache WHERE expires_at < ?", (datetime.now().isoformat(),))
    
    def get_cached_list_metadata(self, list_id: str) -> Optional[Dict[str, Any]]:
        """Get cached list metadata if available and not expired."""
        self._cleanup_expired_cache()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name, description, member_count, follower_count, private, owner_id, created_at
                FROM list_metadata_cache 
                WHERE list_id = ? AND expires_at > ?
            """, (list_id, datetime.now().isoformat()))
            
            result = cursor.fetchone()
            if result:
                return {
                    "name": result[0],
                    "description": result[1],
                    "member_count": result[2],
                    "follower_count": result[3],
                    "private": bool(result[4]),
                    "owner_id": result[5],
                    "created_at": result[6]
                }
        return None
    
    def cache_list_metadata(self, list_id: str, metadata: Dict[str, Any]):
        """Cache list metadata."""
        now = datetime.now()
        expires_at = now + timedelta(days=self.cache_ttl_days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO list_metadata_cache 
                (list_id, name, description, member_count, follower_count, private, owner_id, created_at, cached_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                list_id,
                metadata.get('name'),
                metadata.get('description'),
                metadata.get('member_count'),
                metadata.get('follower_count'),
                metadata.get('private', False),
                metadata.get('owner_id'),
                metadata.get('created_at'),
                now.isoformat(),
                expires_at.isoformat()
            ))
    
    def fetch_list_metadata_from_api(self, list_id: str) -> Optional[Dict[str, Any]]:
        """Fetch list metadata from Twitter API."""
        if not self.twitter_client or not self.twitter_client.client:
            logger.warning("Twitter client not available")
            return None
        
        try:
            # Use Twitter API v2 to get list details
            response = self.twitter_client.client.get_list(
                id=list_id,
                list_fields=['id', 'name', 'description', 'member_count', 'follower_count', 'private', 'owner_id', 'created_at']
            )
            
            if response.data:
                list_data = response.data
                metadata = {
                    'name': list_data.name,
                    'description': list_data.description,
                    'member_count': list_data.member_count,
                    'follower_count': list_data.follower_count,
                    'private': list_data.private,
                    'owner_id': list_data.owner_id,
                    'created_at': list_data.created_at.isoformat() if list_data.created_at else None
                }
                
                # Cache the metadata
                self.cache_list_metadata(list_id, metadata)
                logger.info(f"Fetched metadata for list {list_id}: {metadata['member_count']} members")
                return metadata
            
        except tweepy.TooManyRequests:
            logger.warning(f"Rate limited when fetching list {list_id}")
            return None
        except tweepy.Forbidden:
            logger.warning(f"Access forbidden for list {list_id} (may be private)")
            return None
        except Exception as e:
            logger.error(f"Error fetching list metadata for {list_id}: {e}")
            return None
        
        return None
    
    def enrich_list(self, list_id: str) -> Optional[Dict[str, Any]]:
        """Enrich a single list with metadata."""
        # First check cache
        cached = self.get_cached_list_metadata(list_id)
        if cached:
            return cached
        
        # Fetch from API if not cached
        return self.fetch_list_metadata_from_api(list_id)
    
    def enrich_lists_batch(self, list_ids: List[str], delay: float = LIST_ENRICHMENT_DEFAULT_DELAY) -> Dict[str, Any]:
        """Enrich multiple lists with metadata."""
        enriched_count = 0
        failed_count = 0
        cached_count = 0
        
        for list_id in list_ids:
            try:
                # Check cache first
                cached = self.get_cached_list_metadata(list_id)
                if cached:
                    cached_count += 1
                    continue
                
                # Fetch from API
                metadata = self.fetch_list_metadata_from_api(list_id)
                if metadata:
                    enriched_count += 1
                else:
                    failed_count += 1
                
                # Rate limiting delay
                if delay > 0:
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error enriching list {list_id}: {e}")
                failed_count += 1
        
        return {
            "enriched_count": enriched_count,
            "failed_count": failed_count,
            "cached_count": cached_count,
            "total_processed": len(list_ids)
        }
    
    def get_all_list_ids(self) -> List[str]:
        """Get all list IDs from the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM lists WHERE id IS NOT NULL")
            return [row[0] for row in cursor.fetchall()]
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get statistics about list enrichment."""
        with sqlite3.connect(self.db_path) as conn:
            # Total lists
            cursor = conn.execute("SELECT COUNT(*) FROM lists")
            total_lists = cursor.fetchone()[0]
            
            # Enriched lists (with cached metadata)
            cursor = conn.execute("""
                SELECT COUNT(*) FROM list_metadata_cache 
                WHERE expires_at > ?
            """, (datetime.now().isoformat(),))
            enriched_lists = cursor.fetchone()[0]
            
            # Lists with member counts
            cursor = conn.execute("""
                SELECT COUNT(*) FROM list_metadata_cache 
                WHERE member_count IS NOT NULL AND expires_at > ?
            """, (datetime.now().isoformat(),))
            lists_with_counts = cursor.fetchone()[0]
            
            return {
                "total_lists": total_lists,
                "enriched_lists": enriched_lists,
                "lists_with_member_counts": lists_with_counts,
                "enrichment_percentage": (enriched_lists / total_lists * 100) if total_lists > 0 else 0
            } 