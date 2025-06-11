#!/usr/bin/env python3
"""
X API v2 List Members Fetcher

Fetches members from Twitter/X lists using the X API v2.
Supports both public and private lists (with proper authentication).
"""

import os
import time
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ListMember:
    """Represents a member of a Twitter list"""
    id: str
    username: str
    name: str
    description: Optional[str] = None
    profile_image_url: Optional[str] = None
    verified: bool = False
    protected: bool = False
    public_metrics: Optional[Dict] = None
    created_at: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None

@dataclass
class TwitterList:
    """Represents a Twitter list"""
    id: str
    name: str
    description: Optional[str] = None
    member_count: int = 0
    follower_count: int = 0
    private: bool = False
    owner_id: Optional[str] = None
    created_at: Optional[str] = None

class ListMembersFetcher:
    """Fetches members from Twitter/X lists using X API v2"""
    
    def __init__(self, bearer_token: str, db_path: str = "data/x_data.db"):
        self.bearer_token = bearer_token
        self.db_path = db_path
        self.base_url = "https://api.x.com/2"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "TwitterTools/1.0"
        })
        
        # Rate limiting: 75 requests per 15 minutes for list members
        self.rate_limit = {
            'requests_per_window': 75,
            'window_minutes': 15,
            'requests_made': 0,
            'window_start': datetime.now()
        }
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables for storing list data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS twitter_lists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    member_count INTEGER DEFAULT 0,
                    follower_count INTEGER DEFAULT 0,
                    private BOOLEAN DEFAULT 0,
                    owner_id TEXT,
                    created_at TEXT,
                    fetched_at TEXT,
                    last_updated TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS list_members (
                    list_id TEXT,
                    user_id TEXT,
                    username TEXT,
                    name TEXT,
                    description TEXT,
                    profile_image_url TEXT,
                    verified BOOLEAN DEFAULT 0,
                    protected BOOLEAN DEFAULT 0,
                    follower_count INTEGER,
                    following_count INTEGER,
                    tweet_count INTEGER,
                    created_at TEXT,
                    location TEXT,
                    url TEXT,
                    fetched_at TEXT,
                    PRIMARY KEY (list_id, user_id),
                    FOREIGN KEY (list_id) REFERENCES twitter_lists(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_list_members_list_id 
                ON list_members(list_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_list_members_username 
                ON list_members(username)
            """)
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = datetime.now()
        
        # Reset window if 15 minutes have passed
        if now - self.rate_limit['window_start'] > timedelta(minutes=self.rate_limit['window_minutes']):
            self.rate_limit['requests_made'] = 0
            self.rate_limit['window_start'] = now
        
        # Check if we've hit the limit
        if self.rate_limit['requests_made'] >= self.rate_limit['requests_per_window']:
            wait_time = (self.rate_limit['window_start'] + 
                        timedelta(minutes=self.rate_limit['window_minutes']) - now).total_seconds()
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)
                self.rate_limit['requests_made'] = 0
                self.rate_limit['window_start'] = datetime.now()
    
    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make a rate-limited request to the X API"""
        self._check_rate_limit()
        
        try:
            response = self.session.get(url, params=params)
            self.rate_limit['requests_made'] += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited - wait and retry
                reset_time = int(response.headers.get('x-rate-limit-reset', 0))
                wait_time = max(reset_time - int(time.time()), 60)
                logger.warning(f"Rate limited by API. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_request(url, params)
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    def get_list_info(self, list_id: str) -> Optional[TwitterList]:
        """Get information about a Twitter list"""
        url = f"{self.base_url}/lists/{list_id}"
        params = {
            'list.fields': 'id,name,description,member_count,follower_count,private,owner_id,created_at'
        }
        
        data = self._make_request(url, params)
        if not data or 'data' not in data:
            return None
        
        list_data = data['data']
        return TwitterList(
            id=list_data['id'],
            name=list_data['name'],
            description=list_data.get('description'),
            member_count=list_data.get('member_count', 0),
            follower_count=list_data.get('follower_count', 0),
            private=list_data.get('private', False),
            owner_id=list_data.get('owner_id'),
            created_at=list_data.get('created_at')
        )
    
    def get_list_members(self, list_id: str, max_results: int = 100) -> List[ListMember]:
        """
        Get all members of a Twitter list
        
        Args:
            list_id: The ID of the Twitter list
            max_results: Maximum results per request (1-100, default 100)
            
        Returns:
            List of ListMember objects
        """
        url = f"{self.base_url}/lists/{list_id}/members"
        params = {
            'max_results': min(max_results, 100),
            'user.fields': 'id,username,name,description,profile_image_url,verified,protected,public_metrics,created_at,location,url'
        }
        
        members = []
        pagination_token = None
        
        while True:
            if pagination_token:
                params['pagination_token'] = pagination_token
            
            data = self._make_request(url, params)
            if not data or 'data' not in data:
                break
            
            # Process members
            for user_data in data['data']:
                public_metrics = user_data.get('public_metrics', {})
                member = ListMember(
                    id=user_data['id'],
                    username=user_data['username'],
                    name=user_data['name'],
                    description=user_data.get('description'),
                    profile_image_url=user_data.get('profile_image_url'),
                    verified=user_data.get('verified', False),
                    protected=user_data.get('protected', False),
                    public_metrics=public_metrics,
                    created_at=user_data.get('created_at'),
                    location=user_data.get('location'),
                    url=user_data.get('url')
                )
                members.append(member)
            
            # Check for next page
            meta = data.get('meta', {})
            pagination_token = meta.get('next_token')
            if not pagination_token:
                break
            
            logger.info(f"Fetched {len(members)} members so far...")
        
        logger.info(f"Total members fetched: {len(members)}")
        return members
    
    def save_list_and_members(self, list_info: TwitterList, members: List[ListMember]):
        """Save list information and members to database"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Save list info
            conn.execute("""
                INSERT OR REPLACE INTO twitter_lists 
                (id, name, description, member_count, follower_count, private, owner_id, created_at, fetched_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                list_info.id, list_info.name, list_info.description,
                list_info.member_count, list_info.follower_count, list_info.private,
                list_info.owner_id, list_info.created_at, now, now
            ))
            
            # Clear existing members for this list
            conn.execute("DELETE FROM list_members WHERE list_id = ?", (list_info.id,))
            
            # Save members
            for member in members:
                public_metrics = member.public_metrics or {}
                conn.execute("""
                    INSERT INTO list_members 
                    (list_id, user_id, username, name, description, profile_image_url, 
                     verified, protected, follower_count, following_count, tweet_count,
                     created_at, location, url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    list_info.id, member.id, member.username, member.name,
                    member.description, member.profile_image_url, member.verified,
                    member.protected, public_metrics.get('followers_count'),
                    public_metrics.get('following_count'), public_metrics.get('tweet_count'),
                    member.created_at, member.location, member.url, now
                ))
            
            conn.commit()
            logger.info(f"Saved {len(members)} members for list '{list_info.name}'")
    
    def fetch_and_store_list_members(self, list_id: str) -> Tuple[Optional[TwitterList], List[ListMember]]:
        """
        Complete workflow: fetch list info and members, then store in database
        
        Args:
            list_id: The ID of the Twitter list
            
        Returns:
            Tuple of (TwitterList, List[ListMember])
        """
        logger.info(f"Fetching list information for ID: {list_id}")
        
        # Get list information
        list_info = self.get_list_info(list_id)
        if not list_info:
            logger.error(f"Could not fetch list information for ID: {list_id}")
            return None, []
        
        logger.info(f"Found list: '{list_info.name}' with {list_info.member_count} members")
        
        # Get list members
        members = self.get_list_members(list_id)
        
        # Save to database
        if members:
            self.save_list_and_members(list_info, members)
        
        return list_info, members
    
    def get_stored_list_members(self, list_id: str) -> List[Dict]:
        """Get stored list members from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT lm.*, tl.name as list_name 
                FROM list_members lm
                JOIN twitter_lists tl ON lm.list_id = tl.id
                WHERE lm.list_id = ?
                ORDER BY lm.name
            """, (list_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stored_lists(self) -> List[Dict]:
        """Get all stored lists from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM twitter_lists 
                ORDER BY name
            """)
            
            return [dict(row) for row in cursor.fetchall()]

def main():
    """Example usage"""
    # Get bearer token from environment
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    if not bearer_token:
        print("Error: TWITTER_BEARER_TOKEN environment variable not set")
        return
    
    fetcher = ListMembersFetcher(bearer_token)
    
    # Example: Fetch members from a public list
    # Replace with actual list ID
    list_id = "1234567890"  # Example list ID
    
    try:
        list_info, members = fetcher.fetch_and_store_list_members(list_id)
        
        if list_info and members:
            print(f"\nSuccessfully fetched list: {list_info.name}")
            print(f"Members: {len(members)}")
            print(f"Description: {list_info.description}")
            
            # Show first 5 members
            print("\nFirst 5 members:")
            for member in members[:5]:
                print(f"- @{member.username} ({member.name})")
                if member.public_metrics:
                    followers = member.public_metrics.get('followers_count', 0)
                    print(f"  Followers: {followers:,}")
        
    except Exception as e:
        logger.error(f"Error fetching list members: {e}")

if __name__ == "__main__":
    main() 