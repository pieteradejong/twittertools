import sqlite3
import requests
import logging
import time
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import tweepy

logger = logging.getLogger(__name__)

class AlternativeAPIEnrichmentService:
    """Alternative API approaches for tweet enrichment."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
        self.twitter_client = None
        self.nitter_instances = [
            "https://nitter.net",
            "https://nitter.it", 
            "https://nitter.privacydev.net",
            "https://nitter.fdn.fr"
        ]
        self._init_clients()
    
    def _init_clients(self):
        """Initialize various API clients."""
        # Try different Twitter API authentication methods
        self._init_twitter_api_v2()
        self._init_twitter_api_v1()
    
    def _init_twitter_api_v2(self):
        """Initialize Twitter API v2 with different credential combinations."""
        try:
            # Method 1: Bearer Token only (most restrictive)
            bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
            if bearer_token:
                self.twitter_client = tweepy.Client(bearer_token=bearer_token)
                logger.info("✅ Twitter API v2 initialized with Bearer Token")
                return
            
            # Method 2: App credentials for app-only auth
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            if api_key and api_secret:
                # Create app-only auth
                auth = tweepy.AppAuthHandler(api_key, api_secret)
                api = tweepy.API(auth, wait_on_rate_limit=True)
                logger.info("✅ Twitter API v1.1 app-only auth initialized")
                return
                
        except Exception as e:
            logger.warning(f"Failed to initialize Twitter API: {str(e)}")
    
    def _init_twitter_api_v1(self):
        """Initialize Twitter API v1.1 as fallback."""
        try:
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if all([api_key, api_secret, access_token, access_token_secret]):
                auth = tweepy.OAuthHandler(api_key, api_secret)
                auth.set_access_token(access_token, access_token_secret)
                self.api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
                logger.info("✅ Twitter API v1.1 OAuth initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Twitter API v1.1: {str(e)}")
    
    def get_tweet_via_nitter(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet information via Nitter (Twitter frontend)."""
        for nitter_url in self.nitter_instances:
            try:
                url = f"{nitter_url}/i/status/{tweet_id}"
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; TwitterTools/1.0)'
                })
                
                if response.status_code == 200:
                    # Parse Nitter HTML for author info
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Nitter has cleaner HTML structure
                    username_elem = soup.select_one('.username')
                    fullname_elem = soup.select_one('.fullname')
                    avatar_elem = soup.select_one('.avatar img')
                    
                    if username_elem:
                        username = username_elem.get_text(strip=True).replace('@', '')
                        display_name = fullname_elem.get_text(strip=True) if fullname_elem else username
                        avatar_url = avatar_elem.get('src') if avatar_elem else None
                        
                        return {
                            'username': username,
                            'display_name': display_name,
                            'avatar_url': f"{nitter_url}{avatar_url}" if avatar_url else None,
                            'source': f'nitter_{nitter_url.split("//")[1]}'
                        }
                
            except Exception as e:
                logger.debug(f"Nitter instance {nitter_url} failed: {str(e)}")
                continue
        
        return None
    
    def get_tweet_via_api_batch(self, tweet_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple tweets via API in batch (more efficient)."""
        results = {}
        
        if not self.twitter_client:
            return results
        
        # Process in batches of 100 (API limit)
        batch_size = 100
        for i in range(0, len(tweet_ids), batch_size):
            batch = tweet_ids[i:i + batch_size]
            
            try:
                # Use API v2 batch lookup
                tweets = self.twitter_client.get_tweets(
                    ids=batch,
                    expansions=['author_id'],
                    user_fields=['username', 'name', 'profile_image_url', 'verified'],
                    tweet_fields=['created_at']
                )
                
                if tweets.data and tweets.includes and 'users' in tweets.includes:
                    # Create user lookup
                    users_by_id = {user.id: user for user in tweets.includes['users']}
                    
                    for tweet in tweets.data:
                        author = users_by_id.get(tweet.author_id)
                        if author:
                            results[tweet.id] = {
                                'username': author.username,
                                'display_name': author.name,
                                'avatar_url': author.profile_image_url,
                                'verified': author.verified or False,
                                'source': 'api_batch'
                            }
                
                # Rate limiting
                time.sleep(1)
                
            except tweepy.TooManyRequests:
                logger.warning("Rate limit hit, waiting...")
                time.sleep(15 * 60)  # Wait 15 minutes
            except Exception as e:
                logger.warning(f"Batch API call failed: {str(e)}")
        
        return results
    
    def enrich_with_multiple_methods(self, limit: int = 100) -> Dict[str, int]:
        """Try multiple enrichment methods in order of preference."""
        stats = {
            'api_batch': 0,
            'nitter': 0,
            'text_patterns': 0,
            'total_processed': 0
        }
        
        with sqlite3.connect(self.db_path) as conn:
            # Get tweets that need enrichment
            cursor = conn.execute("""
                SELECT tweet_id, full_text 
                FROM likes 
                WHERE author_username IS NULL 
                LIMIT ?
            """, (limit,))
            
            tweets_to_process = cursor.fetchall()
            tweet_ids = [row[0] for row in tweets_to_process]
            
            logger.info(f"Processing {len(tweet_ids)} tweets with multiple methods")
            
            # Method 1: Try API batch first (most reliable)
            if self.twitter_client and len(tweet_ids) > 0:
                logger.info("🔄 Trying API batch method...")
                api_results = self.get_tweet_via_api_batch(tweet_ids)
                
                for tweet_id, author_info in api_results.items():
                    conn.execute("""
                        UPDATE likes 
                        SET author_username = ?, author_id = ?
                        WHERE tweet_id = ?
                    """, (author_info['username'], None, tweet_id))
                    
                    stats['api_batch'] += 1
                
                # Remove successfully processed tweets
                tweet_ids = [tid for tid in tweet_ids if tid not in api_results]
            
            # Method 2: Try Nitter for remaining tweets
            if tweet_ids:
                logger.info(f"🔄 Trying Nitter method for {len(tweet_ids)} remaining tweets...")
                for tweet_id in tweet_ids[:20]:  # Limit to avoid overwhelming Nitter
                    author_info = self.get_tweet_via_nitter(tweet_id)
                    if author_info:
                        conn.execute("""
                            UPDATE likes 
                            SET author_username = ?, author_id = ?
                            WHERE tweet_id = ?
                        """, (author_info['username'], None, tweet_id))
                        
                        stats['nitter'] += 1
                    
                    time.sleep(1)  # Be nice to Nitter
            
            # Method 3: Text pattern extraction for remaining tweets
            remaining_tweets = [(tid, text) for tid, text in tweets_to_process 
                              if tid in tweet_ids]
            
            if remaining_tweets:
                logger.info(f"🔄 Trying text pattern extraction for {len(remaining_tweets)} tweets...")
                from text_based_enrichment import TextBasedEnrichmentService
                text_service = TextBasedEnrichmentService(self.db_path)
                
                for tweet_id, full_text in remaining_tweets:
                    author_info = text_service.extract_author_from_text(full_text, tweet_id)
                    if author_info and author_info['confidence'] >= 0.7:
                        conn.execute("""
                            UPDATE likes 
                            SET author_username = ?, author_id = ?
                            WHERE tweet_id = ?
                        """, (author_info['username'], None, tweet_id))
                        
                        stats['text_patterns'] += 1
            
            conn.commit()
            stats['total_processed'] = len(tweets_to_process)
        
        logger.info(f"Multi-method enrichment completed: {stats}")
        return stats 