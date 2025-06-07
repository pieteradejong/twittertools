#!/usr/bin/env python3
"""
Test script for semantic classification of likes
"""

import logging
from src.semantic_classifier import SemanticTweetClassifier

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_classification():
    """Test semantic classification on a small sample of likes."""
    
    # Initialize classifier
    classifier = SemanticTweetClassifier(similarity_threshold=0.25)
    
    # Get a small sample of likes for testing
    likes = classifier.get_likes_from_db(limit=10)
    
    if not likes:
        print("No likes found in database. Please ensure you have likes data.")
        return
    
    print(f"\n🔍 Testing semantic classification on {len(likes)} likes...")
    print("=" * 60)
    
    # Classify the sample
    classifications = classifier.classify_tweets_batch(likes, batch_size=5)
    
    # Display results
    for result in classifications:
        print(f"\n📝 Tweet: {result['text'][:100]}...")
        print(f"🎯 Topic Scores:")
        
        # Sort scores by value
        sorted_scores = sorted(result['all_scores'].items(), key=lambda x: x[1], reverse=True)
        
        for topic, score in sorted_scores:
            emoji = "🟢" if score >= classifier.similarity_threshold else "🔴"
            print(f"   {emoji} {topic}: {score:.3f}")
        
        if result['assigned_topics']:
            assigned = ", ".join([f"{topic} ({score:.2f})" for topic, score in result['assigned_topics'].items()])
            print(f"✅ Assigned Topics: {assigned}")
        else:
            print("❌ No topics assigned (all scores below threshold)")
        
        print("-" * 40)
    
    # Save classifications to database
    print(f"\n💾 Saving classifications to database...")
    classifier.save_classifications(classifications)
    
    # Show topic summary
    topics = classifier.get_available_topics()
    if topics:
        print(f"\n📊 Topic Summary:")
        for topic_info in topics:
            print(f"   {topic_info['topic']}: {topic_info['count']} items (avg: {topic_info['avg_score']:.3f})")
    
    print(f"\n✅ Test completed successfully!")

if __name__ == "__main__":
    test_classification() 