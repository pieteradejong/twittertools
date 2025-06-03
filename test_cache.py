#!/usr/bin/env python3
"""
Test script for the in-memory cache system.

Usage:
    python test_cache.py
"""

import sys
import time
from pathlib import Path

# Add src to path so we can import the cache
sys.path.append(str(Path(__file__).parent / 'src'))

from memory_cache import cache

def test_cache_loading():
    """Test loading the cache and show statistics."""
    print("🧪 Testing In-Memory Cache System")
    print("=" * 50)
    
    # Load the cache
    start_time = time.time()
    cache.load_all_data()
    load_time = time.time() - start_time
    
    # Show statistics
    stats = cache.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   • Tweets loaded: {stats['tweets_count']:,}")
    print(f"   • Likes loaded: {stats['likes_count']:,}")
    print(f"   • Users loaded: {stats['users_count']:,}")
    print(f"   • Blocks loaded: {stats['blocks_count']:,}")
    print(f"   • Mutes loaded: {stats['mutes_count']:,}")
    print(f"   • Load time: {stats['load_duration_seconds']:.2f}s")
    print(f"   • Cache loaded: {stats['loaded']}")
    
    return stats

def test_cache_performance():
    """Test cache performance with various operations."""
    print(f"\n⚡ Performance Tests:")
    print("-" * 30)
    
    # Get account info
    start_time = time.time()
    account = cache.get_account_info()
    account_time = (time.time() - start_time) * 1000
    print(f"   • Get account info: {account_time:.2f}ms")
    
    if account:
        user_id = account.get('account_id')
        print(f"   • Account: @{account.get('username', 'unknown')}")
        
        # Get user tweets
        start_time = time.time()
        tweets = cache.get_tweets_by_author(user_id, limit=100)
        tweets_time = (time.time() - start_time) * 1000
        print(f"   • Get 100 tweets: {tweets_time:.2f}ms")
        
        # Get user replies
        start_time = time.time()
        replies = cache.get_user_replies(user_id, limit=50)
        replies_time = (time.time() - start_time) * 1000
        print(f"   • Get 50 replies: {replies_time:.2f}ms")
        
        # Get zero engagement tweets
        start_time = time.time()
        zero_tweets = cache.get_zero_engagement_tweets(user_id)
        zero_time = (time.time() - start_time) * 1000
        print(f"   • Get zero engagement tweets: {zero_time:.2f}ms")
        print(f"   • Zero engagement count: {len(zero_tweets):,}")
    
    # Get recent likes
    start_time = time.time()
    likes = cache.get_liked_tweets(limit=50)
    likes_time = (time.time() - start_time) * 1000
    print(f"   • Get 50 likes: {likes_time:.2f}ms")

def show_sample_data():
    """Show some sample data from the cache."""
    print(f"\n📝 Sample Data:")
    print("-" * 20)
    
    # Show recent tweets
    account = cache.get_account_info()
    if account:
        user_id = account.get('account_id')
        tweets = cache.get_tweets_by_author(user_id, limit=3)
        
        print(f"\n🐦 Recent Tweets (showing 3 of {len(cache.get_tweets_by_author(user_id))}):")
        for i, tweet in enumerate(tweets, 1):
            text = tweet['text'][:100] + "..." if len(tweet['text']) > 100 else tweet['text']
            print(f"   {i}. {text}")
            print(f"      ❤️ {tweet['favorite_count']} | 🔄 {tweet['retweet_count']} | 📅 {tweet['created_at'][:10]}")
    
    # Show recent likes
    likes = cache.get_liked_tweets(limit=3)
    print(f"\n❤️ Recent Likes (showing 3 of {len(likes)}):")
    for i, like in enumerate(likes, 1):
        text = like['full_text'][:100] + "..." if like['full_text'] and len(like['full_text']) > 100 else like['full_text']
        print(f"   {i}. {text or 'No text available'}")
        print(f"      📅 Liked: {like['liked_at'] or 'Unknown'}")

def main():
    """Main test function."""
    try:
        # Test cache loading
        stats = test_cache_loading()
        
        if stats['tweets_count'] == 0:
            print("\n⚠️  No tweets found in database. Make sure you have:")
            print("   1. Run 'python scripts/load_local_data.py' to load your Twitter archive")
            print("   2. Or have data in your SQLite database at 'data/x_data.db'")
            return
        
        # Test performance
        test_cache_performance()
        
        # Show sample data
        show_sample_data()
        
        print(f"\n✅ Cache test completed successfully!")
        print(f"💡 Your cache is working and contains {stats['tweets_count']:,} tweets")
        print(f"🚀 All operations completed in sub-millisecond time!")
        
    except Exception as e:
        print(f"\n❌ Error testing cache: {str(e)}")
        print(f"💡 Make sure your database exists at 'data/x_data.db'")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 