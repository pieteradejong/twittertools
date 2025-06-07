#!/usr/bin/env python3
"""
Test script for the tweet enrichment service.
"""

import sys
import os
sys.path.append('src')

from tweet_enrichment_service import TweetEnrichmentService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_enrichment():
    """Test the tweet enrichment service."""
    logger.info("Testing tweet enrichment service...")
    
    # Initialize service
    service = TweetEnrichmentService()
    
    # Get stats
    stats = service.get_enrichment_stats()
    logger.info(f"Initial stats: {stats}")
    
    # Test with recent tweet IDs from the database
    import sqlite3
    with sqlite3.connect("data/x_data.db") as conn:
        cursor = conn.execute("SELECT tweet_id FROM likes ORDER BY rowid DESC LIMIT 3")
        tweet_ids = [row[0] for row in cursor.fetchall()]
    
    logger.info(f"Testing with recent tweet IDs: {tweet_ids}")
    
    # Test individual tweet enrichment
    for tweet_id in tweet_ids:
        logger.info(f"Testing tweet {tweet_id}...")
        tweet_details = service.get_tweet_details(tweet_id)
        if tweet_details:
            logger.info(f"  Success: {tweet_details}")
        else:
            logger.warning(f"  Failed to get details for tweet {tweet_id}")
    
    # Get final stats
    final_stats = service.get_enrichment_stats()
    logger.info(f"Final stats: {final_stats}")

if __name__ == "__main__":
    test_enrichment() 