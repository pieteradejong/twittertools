import sqlite3
import requests
import re
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)

class WebScrapingEnrichmentService:
    """Scrape Twitter/X web pages to get author information."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
        self.session = requests.Session()
        
        # Set up headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def scrape_tweet_author(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Scrape author information from a tweet URL."""
        url = f"https://twitter.com/i/web/status/{tweet_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if 'author' in data:
                        author = data['author']
                        return {
                            'username': author.get('additionalName', '').replace('@', ''),
                            'display_name': author.get('name', ''),
                            'avatar_url': author.get('image', ''),
                            'source': 'json_ld'
                        }
                except json.JSONDecodeError:
                    continue
            
            # Method 2: Look for meta tags
            meta_tags = {
                'twitter:creator': soup.find('meta', {'name': 'twitter:creator'}),
                'twitter:site': soup.find('meta', {'name': 'twitter:site'}),
                'author': soup.find('meta', {'name': 'author'}),
            }
            
            username = None
            for tag_name, tag in meta_tags.items():
                if tag and tag.get('content'):
                    content = tag.get('content').replace('@', '')
                    if content and len(content) > 0:
                        username = content
                        break
            
            if username:
                return {
                    'username': username,
                    'display_name': username,
                    'avatar_url': None,
                    'source': 'meta_tags'
                }
            
            # Method 3: Look for specific CSS selectors (this may break if Twitter changes their HTML)
            author_selectors = [
                '[data-testid="User-Name"]',
                '[data-testid="UserName"]',
                '.css-1dbjc4n .css-901oao .css-16my406',
                'a[role="link"][href^="/"]'
            ]
            
            for selector in author_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and text.startswith('@'):
                        username = text.replace('@', '')
                        return {
                            'username': username,
                            'display_name': username,
                            'avatar_url': None,
                            'source': 'css_selector'
                        }
            
            logger.debug(f"No author information found for tweet {tweet_id}")
            return None
            
        except requests.RequestException as e:
            logger.warning(f"Failed to scrape tweet {tweet_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping tweet {tweet_id}: {str(e)}")
            return None
    
    def enrich_likes_batch(self, limit: int = 50, delay: float = 2.0) -> int:
        """Enrich likes using web scraping with rate limiting."""
        enriched_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            # Get likes without author info
            cursor = conn.execute("""
                SELECT tweet_id 
                FROM likes 
                WHERE author_username IS NULL 
                LIMIT ?
            """, (limit,))
            
            tweet_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"Starting web scraping for {len(tweet_ids)} tweets")
            
            for i, tweet_id in enumerate(tweet_ids):
                logger.info(f"Scraping tweet {i+1}/{len(tweet_ids)}: {tweet_id}")
                
                author_info = self.scrape_tweet_author(tweet_id)
                
                if author_info:
                    # Update the likes table
                    conn.execute("""
                        UPDATE likes 
                        SET author_username = ?, author_id = ?
                        WHERE tweet_id = ?
                    """, (author_info['username'], None, tweet_id))
                    
                    # Cache in enrichment table
                    conn.execute("""
                        INSERT OR REPLACE INTO tweet_enrichment_cache 
                        (tweet_id, author_username, author_display_name, 
                         author_avatar_url, cached_at, expires_at, source)
                        VALUES (?, ?, ?, ?, datetime('now'), 
                                datetime('now', '+30 days'), ?)
                    """, (
                        tweet_id,
                        author_info['username'],
                        author_info['display_name'],
                        author_info.get('avatar_url'),
                        author_info['source']
                    ))
                    
                    enriched_count += 1
                    logger.info(f"  ✅ Found author: @{author_info['username']}")
                else:
                    logger.info(f"  ❌ No author found")
                
                # Rate limiting
                if i < len(tweet_ids) - 1:  # Don't delay after the last request
                    time.sleep(delay)
            
            conn.commit()
        
        logger.info(f"Web scraping completed: {enriched_count}/{len(tweet_ids)} tweets enriched")
        return enriched_count 