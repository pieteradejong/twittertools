#!/usr/bin/env python3
"""
Test script for new enrichment methods that circumvent API access limitations.
"""

import sqlite3
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from text_based_enrichment import TextBasedEnrichmentService
from web_scraping_enrichment import WebScrapingEnrichmentService
from alternative_api_enrichment import AlternativeAPIEnrichmentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_text_pattern_enrichment():
    """Test text-based pattern enrichment."""
    print("\n🔍 Testing Text Pattern Enrichment")
    print("=" * 50)
    
    service = TextBasedEnrichmentService()
    
    # Test individual pattern extraction
    test_tweets = [
        ("RT @elonmusk: Tesla is the future!", "1234567890"),
        ('"Great insights on AI" - @sama', "1234567891"),
        ("I am @johndoe and I love coding", "1234567892"),
        ("Follow me @twitter for updates", "1234567893"),
        ("Regular tweet without patterns", "1234567894"),
    ]
    
    print("Testing pattern extraction on sample tweets:")
    for tweet_text, tweet_id in test_tweets:
        result = service.extract_author_from_text(tweet_text, tweet_id)
        if result:
            print(f"✅ '{tweet_text[:30]}...' -> @{result['username']} (confidence: {result['confidence']})")
        else:
            print(f"❌ '{tweet_text[:30]}...' -> No pattern found")
    
    # Test batch enrichment
    print(f"\n📊 Running batch enrichment on database...")
    enriched_count = service.enrich_likes_from_text()
    print(f"✅ Enriched {enriched_count} likes using text patterns")

def test_web_scraping_enrichment():
    """Test web scraping enrichment (limited to avoid overwhelming servers)."""
    print("\n🌐 Testing Web Scraping Enrichment")
    print("=" * 50)
    
    service = WebScrapingEnrichmentService()
    
    # Test with a small sample
    print("⚠️  Running limited web scraping test (5 tweets max)...")
    enriched_count = service.enrich_likes_batch(limit=5, delay=3.0)
    print(f"✅ Enriched {enriched_count} likes using web scraping")

def test_multi_method_enrichment():
    """Test multi-method enrichment approach."""
    print("\n🚀 Testing Multi-Method Enrichment")
    print("=" * 50)
    
    service = AlternativeAPIEnrichmentService()
    
    # Test with a small sample
    print("🔄 Running multi-method enrichment (20 tweets max)...")
    stats = service.enrich_with_multiple_methods(limit=20)
    
    print("📊 Multi-method enrichment results:")
    for method, count in stats.items():
        print(f"  • {method}: {count}")

def show_enrichment_stats():
    """Show current enrichment statistics."""
    print("\n📈 Current Enrichment Statistics")
    print("=" * 50)
    
    db_path = Path("data/x_data.db")
    if not db_path.exists():
        print("❌ Database not found!")
        return
    
    with sqlite3.connect(db_path) as conn:
        # Total likes
        cursor = conn.execute("SELECT COUNT(*) FROM likes")
        total_likes = cursor.fetchone()[0]
        
        # Likes with author info
        cursor = conn.execute("SELECT COUNT(*) FROM likes WHERE author_username IS NOT NULL")
        enriched_likes = cursor.fetchone()[0]
        
        # Enrichment coverage
        coverage = (enriched_likes / total_likes * 100) if total_likes > 0 else 0
        
        print(f"📝 Total likes: {total_likes:,}")
        print(f"✅ Enriched likes: {enriched_likes:,}")
        print(f"📊 Coverage: {coverage:.1f}%")
        print(f"🔄 Remaining: {total_likes - enriched_likes:,}")
        
        # Show sample enriched tweets
        cursor = conn.execute("""
            SELECT tweet_id, author_username, full_text
            FROM likes 
            WHERE author_username IS NOT NULL 
            LIMIT 5
        """)
        
        print(f"\n📋 Sample enriched tweets:")
        for row in cursor.fetchall():
            tweet_id, username, text = row
            print(f"  • @{username}: {text[:60]}...")

def main():
    """Run all enrichment tests."""
    print("🚀 Twitter Tools - New Enrichment Methods Test")
    print("=" * 60)
    
    # Show current stats
    show_enrichment_stats()
    
    # Test text patterns (safe and fast)
    test_text_pattern_enrichment()
    
    # Ask user before web scraping
    print(f"\n⚠️  Web scraping test will make HTTP requests to Twitter/Nitter.")
    response = input("Continue with web scraping test? (y/N): ").lower().strip()
    if response == 'y':
        test_web_scraping_enrichment()
    else:
        print("⏭️  Skipping web scraping test")
    
    # Test multi-method approach
    test_multi_method_enrichment()
    
    # Show final stats
    print(f"\n" + "=" * 60)
    show_enrichment_stats()
    
    print(f"\n🎉 Testing completed!")
    print(f"\n💡 API Access Improvement Strategies:")
    print(f"   1. ✅ Text Pattern Extraction (No API needed)")
    print(f"   2. ✅ Web Scraping via Nitter (API alternative)")
    print(f"   3. ✅ Multi-method fallback approach")
    print(f"   4. 🔄 Batch API calls (when available)")
    print(f"   5. 💾 Aggressive caching (30-day TTL)")

if __name__ == "__main__":
    main() 