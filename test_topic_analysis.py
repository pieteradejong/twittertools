#!/usr/bin/env python3
"""
Test script for the new modular topic analysis functionality
"""

import logging
from src.topic_analyzer import (
    TopicAnalyzer, 
    DataSource, 
    TopicFilter,
    analyze_tweets_by_topic,
    analyze_likes_by_topic,
    get_topic_overview,
    search_content_semantically
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_topic_analyzer():
    """Test the modular topic analyzer functionality."""
    
    print("🔬 Testing Modular Topic Analysis System")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = TopicAnalyzer(similarity_threshold=0.25)
    
    # Test 1: Get topic overview
    print("\n📊 Getting topic overview...")
    overview = analyzer.get_topic_distribution()
    print(f"Total items: {overview['total_items']}")
    print(f"Total topics: {overview['total_topics']}")
    print(f"Threshold: {overview['threshold']}")
    
    for topic in overview['topics'][:3]:  # Show top 3 topics
        print(f"  • {topic['topic']}: {topic['count']} items ({topic['percentage']}%)")
    
    # Test 2: Analyze different data sources
    print("\n🔍 Analyzing different data sources...")
    
    data_sources = [DataSource.TWEETS, DataSource.LIKES, DataSource.REPLIES]
    
    for source in data_sources:
        print(f"\n--- Analyzing {source.value.upper()} ---")
        try:
            results = analyzer.analyze_data_source(source, limit=5)
            print(f"Analyzed {len(results)} {source.value}")
            
            if results:
                # Show first result
                result = results[0]
                print(f"Sample: {result.text[:100]}...")
                print(f"Topics: {result.assigned_topics}")
                print(f"Max score: {result.max_score:.3f}")
        except Exception as e:
            print(f"Error analyzing {source.value}: {e}")
    
    # Test 3: Topic filtering
    print("\n🎯 Testing topic filtering...")
    
    # Filter likes by technology topic
    tech_filter = TopicFilter(
        topics=["technology"],
        min_score=0.3,
        max_results=5,
        sort_by="score"
    )
    
    tech_results = analyzer.filter_by_topics(DataSource.LIKES, tech_filter)
    print(f"Found {len(tech_results)} technology-related likes")
    
    for result in tech_results[:2]:  # Show first 2
        print(f"  • {result['text'][:80]}... (score: {result['score']:.3f})")
    
    # Test 4: Semantic search
    print("\n🔎 Testing semantic search...")
    
    search_queries = [
        "artificial intelligence and machine learning",
        "Miami beaches and nightlife",
        "political elections and voting"
    ]
    
    for query in search_queries:
        print(f"\nSearching for: '{query}'")
        search_results = analyzer.semantic_search(query, limit=3)
        print(f"Found {len(search_results)} results")
        
        for result in search_results[:1]:  # Show first result
            print(f"  • {result['text'][:80]}... (similarity: {result['similarity_score']:.3f})")
    
    # Test 5: Add custom topic
    print("\n➕ Testing custom topic addition...")
    
    try:
        analyzer.add_custom_topic("crypto", [
            "cryptocurrency and blockchain technology",
            "bitcoin ethereum and digital assets",
            "decentralized finance and NFTs"
        ])
        print("✅ Successfully added 'crypto' topic")
        
        # Test the new topic
        crypto_filter = TopicFilter(
            topics=["crypto"],
            min_score=0.2,
            max_results=3
        )
        
        crypto_results = analyzer.filter_by_topics(DataSource.LIKES, crypto_filter)
        print(f"Found {len(crypto_results)} crypto-related items")
        
    except Exception as e:
        print(f"❌ Error adding custom topic: {e}")
    
    # Test 6: Export functionality
    print("\n💾 Testing export functionality...")
    
    try:
        export_path = analyzer.export_topic_analysis(DataSource.LIKES, "json")
        print(f"✅ Exported analysis to: {export_path}")
    except Exception as e:
        print(f"❌ Export error: {e}")

def test_convenience_functions():
    """Test the convenience functions."""
    
    print("\n🚀 Testing convenience functions...")
    print("-" * 40)
    
    # Test convenience functions
    print("\n1. Analyzing tweets by topic (technology)...")
    tech_tweets = analyze_tweets_by_topic("technology", min_score=0.3, limit=3)
    print(f"Found {len(tech_tweets)} technology tweets")
    
    print("\n2. Analyzing likes by topic (politics)...")
    politics_likes = analyze_likes_by_topic("politics", min_score=0.3, limit=3)
    print(f"Found {len(politics_likes)} politics likes")
    
    print("\n3. Getting topic overview...")
    overview = get_topic_overview()
    print(f"Overview: {overview['total_items']} items across {overview['total_topics']} topics")
    
    print("\n4. Semantic search...")
    search_results = search_content_semantically("Miami culture and events", limit=2)
    print(f"Found {len(search_results)} results for Miami search")

def main():
    """Run all tests."""
    
    try:
        test_topic_analyzer()
        test_convenience_functions()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("\n💡 Usage Tips:")
        print("  • Use the new API endpoints at /api/topics/*")
        print("  • Frontend components: TopicFilter and TopicAnalysisView")
        print("  • Navigate to 'Topic Analysis' tabs in the UI")
        print("  • Add custom topics for your specific use cases")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 