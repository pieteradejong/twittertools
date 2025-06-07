#!/usr/bin/env python3
"""
Migration script to add author fields to the likes table and populate them.
This script will:
1. Add author_id and author_username columns to the likes table
2. Extract author usernames from existing expanded_url fields
3. Update the likes table with the extracted author information
"""

import sqlite3
import re
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_author_from_url(expanded_url):
    """Extract username from Twitter URL like https://twitter.com/username/status/123"""
    if not expanded_url:
        return None, None
    
    # Match Twitter URLs: twitter.com/username/status/id or x.com/username/status/id
    pattern = r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
    match = re.search(pattern, expanded_url)
    
    if match:
        username = match.group(1)
        # Filter out invalid usernames (Twitter usernames can't contain certain chars)
        if username and not any(char in username for char in ['?', '&', '=', '#']):
            return None, username  # We don't have author_id from URL, only username
    
    return None, None

def migrate_likes_table():
    """Migrate the likes table to include author information."""
    db_path = Path("data/x_data.db")
    
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if the columns already exist
            cursor.execute("PRAGMA table_info(likes)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'author_id' in columns and 'author_username' in columns:
                logger.info("Author columns already exist in likes table")
            else:
                # Add the new columns
                logger.info("Adding author_id and author_username columns to likes table...")
                cursor.execute("ALTER TABLE likes ADD COLUMN author_id TEXT")
                cursor.execute("ALTER TABLE likes ADD COLUMN author_username TEXT")
                logger.info("Columns added successfully")
            
            # Get all likes with expanded_url
            cursor.execute("SELECT tweet_id, expanded_url FROM likes WHERE expanded_url IS NOT NULL")
            likes_with_urls = cursor.fetchall()
            
            logger.info(f"Found {len(likes_with_urls)} likes with URLs to process")
            
            updated_count = 0
            for tweet_id, expanded_url in likes_with_urls:
                author_id, author_username = extract_author_from_url(expanded_url)
                
                if author_username:
                    cursor.execute("""
                        UPDATE likes 
                        SET author_id = ?, author_username = ? 
                        WHERE tweet_id = ?
                    """, (author_id, author_username, tweet_id))
                    updated_count += 1
            
            conn.commit()
            logger.info(f"Successfully updated {updated_count} likes with author information")
            
            # Show statistics
            cursor.execute("SELECT COUNT(*) FROM likes")
            total_likes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM likes WHERE author_username IS NOT NULL")
            likes_with_authors = cursor.fetchone()[0]
            
            logger.info(f"Migration complete:")
            logger.info(f"  Total likes: {total_likes}")
            logger.info(f"  Likes with author info: {likes_with_authors}")
            logger.info(f"  Coverage: {(likes_with_authors/total_likes*100):.1f}%")
            
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting likes table migration...")
    success = migrate_likes_table()
    
    if success:
        logger.info("Migration completed successfully!")
    else:
        logger.error("Migration failed!")
        exit(1) 