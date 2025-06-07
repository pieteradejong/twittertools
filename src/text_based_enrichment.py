import sqlite3
import re
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class TextBasedEnrichmentService:
    """Extract author information from tweet text and patterns."""
    
    def __init__(self, db_path: str = "data/x_data.db"):
        self.db_path = Path(db_path)
    
    def extract_author_from_text(self, tweet_text: str, tweet_id: str) -> Optional[Dict[str, str]]:
        """Extract potential author information from tweet text."""
        if not tweet_text:
            return None
        
        # Pattern 1: "RT @username:" (retweets)
        rt_match = re.search(r'RT @([a-zA-Z0-9_]+):', tweet_text)
        if rt_match:
            username = rt_match.group(1)
            return {
                'username': username,
                'display_name': username,
                'source': 'retweet_pattern',
                'confidence': 0.9
            }
        
        # Pattern 2: Quoted tweets often start with username
        quote_patterns = [
            r'^"([^"]+)" - @([a-zA-Z0-9_]+)',  # "Quote" - @username
            r'^([^:]+): "([^"]+)"',            # Name: "quote"
            r'@([a-zA-Z0-9_]+) says:',         # @username says:
        ]
        
        for pattern in quote_patterns:
            match = re.search(pattern, tweet_text)
            if match:
                if len(match.groups()) >= 2:
                    username = match.group(2) if '@' in pattern else match.group(1)
                    return {
                        'username': username,
                        'display_name': match.group(1) if len(match.groups()) >= 2 else username,
                        'source': 'quote_pattern',
                        'confidence': 0.7
                    }
        
        # Pattern 3: Self-referential tweets
        self_patterns = [
            r'I am ([a-zA-Z0-9_]+)',
            r'My name is ([^.!?]+)',
            r'Follow me @([a-zA-Z0-9_]+)',
        ]
        
        for pattern in self_patterns:
            match = re.search(pattern, tweet_text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                return {
                    'username': name.replace(' ', '').lower(),
                    'display_name': name,
                    'source': 'self_reference',
                    'confidence': 0.6
                }
        
        return None
    
    def enrich_likes_from_text(self) -> int:
        """Enrich likes using text-based extraction."""
        enriched_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            # Get likes without author info
            cursor = conn.execute("""
                SELECT tweet_id, full_text 
                FROM likes 
                WHERE author_username IS NULL AND full_text IS NOT NULL
            """)
            
            likes_to_process = cursor.fetchall()
            logger.info(f"Processing {len(likes_to_process)} likes for text-based enrichment")
            
            for tweet_id, full_text in likes_to_process:
                author_info = self.extract_author_from_text(full_text, tweet_id)
                
                if author_info and author_info['confidence'] >= 0.7:
                    # Update the likes table
                    conn.execute("""
                        UPDATE likes 
                        SET author_username = ?, author_id = ?
                        WHERE tweet_id = ?
                    """, (author_info['username'], None, tweet_id))
                    
                    enriched_count += 1
                    logger.debug(f"Enriched tweet {tweet_id} with username {author_info['username']} (confidence: {author_info['confidence']})")
            
            conn.commit()
        
        logger.info(f"Text-based enrichment completed: {enriched_count} likes enriched")
        return enriched_count 