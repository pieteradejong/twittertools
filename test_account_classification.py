#!/usr/bin/env python3
"""
Test script for account classification functionality
"""

import logging
from src.account_classifier import AccountClassifier, ClassificationMethod

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_account_classification():
    """Test account classification on a sample of following accounts."""
    
    print("🔍 Testing Account Classification System")
    print("=" * 60)
    
    # Initialize classifier
    classifier = AccountClassifier()
    
    # Test 1: Get available classification methods
    print("\n📋 Available Classification Methods:")
    methods = [method.value for method in ClassificationMethod]
    for method in methods:
        print(f"  • {method}")
    
    # Test 2: Get profile categories
    print("\n🏷️ Available Profile Categories:")
    for category, patterns in classifier.profile_patterns.items():
        display_name = classifier._format_profile_category(category)
        print(f"  • {display_name}: {len(patterns)} patterns")
        print(f"    Examples: {', '.join(patterns[:3])}...")
    
    # Test 3: Classify a small sample of following accounts
    print("\n👥 Testing Classification on Following Accounts...")
    
    # Get a small sample for testing
    following_accounts = classifier._get_following_accounts(limit=10)
    
    if not following_accounts:
        print("❌ No following accounts found. Please ensure you have relationship data.")
        return
    
    print(f"Found {len(following_accounts)} accounts to test with")
    
    # Test different classification methods
    methods_to_test = [ClassificationMethod.PROFILE_BASED, ClassificationMethod.HYBRID]
    
    for method in methods_to_test:
        print(f"\n🔬 Testing {method.value.upper()} classification...")
        print("-" * 40)
        
        try:
            # Classify first 3 accounts
            for i, account in enumerate(following_accounts[:3]):
                print(f"\n{i+1}. Classifying: {account['display_name'] or account['username'] or account['id']}")
                
                classification = classifier.classify_account(account['id'], method)
                
                print(f"   Profile Category: {classification.profile_category}")
                print(f"   Primary Topics: {', '.join(classification.primary_topics) if classification.primary_topics else 'None'}")
                print(f"   Suggested Lists: {', '.join(classification.suggested_lists)}")
                print(f"   Confidence Score: {classification.confidence_score:.2f}")
                print(f"   Reasons: {'; '.join(classification.classification_reasons[:2])}")
                
        except Exception as e:
            print(f"❌ Error with {method.value} classification: {e}")
    
    # Test 4: Generate list suggestions
    print(f"\n📝 Testing List Suggestions...")
    print("-" * 40)
    
    try:
        # Classify all following accounts (or limit for testing)
        classifications = classifier.classify_all_following(
            method=ClassificationMethod.PROFILE_BASED, 
            limit=20  # Limit for testing
        )
        
        if classifications:
            print(f"Successfully classified {len(classifications)} accounts")
            
            # Generate list suggestions
            suggestions = classifier.suggest_lists(
                classifications, 
                min_members_per_list=2,  # Lower threshold for testing
                max_lists=10
            )
            
            print(f"\n💡 Generated {len(suggestions)} list suggestions:")
            
            for i, suggestion in enumerate(suggestions[:5], 1):  # Show top 5
                print(f"\n{i}. {suggestion.list_name}")
                print(f"   Category: {suggestion.category}")
                print(f"   Members: {suggestion.member_count}")
                print(f"   Confidence: {suggestion.confidence_score:.2f}")
                print(f"   Reason: {suggestion.creation_reason}")
                
                # Show first few members
                if suggestion.members:
                    member_names = [m['display_name'] for m in suggestion.members[:3]]
                    print(f"   Sample Members: {', '.join(member_names)}")
        else:
            print("❌ No accounts were successfully classified")
            
    except Exception as e:
        print(f"❌ Error generating list suggestions: {e}")
    
    # Test 5: Show classification statistics
    print(f"\n📊 Classification Statistics:")
    print("-" * 40)
    
    if 'classifications' in locals() and classifications:
        # Count by profile category
        category_counts = {}
        topic_counts = {}
        
        for classification in classifications:
            # Count profile categories
            category = classification.profile_category
            category_counts[category] = category_counts.get(category, 0) + 1
            
            # Count topics
            for topic in classification.primary_topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        print("Profile Categories:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            display_name = classifier._format_profile_category(category) if category != "unknown" else "Unknown"
            print(f"  • {display_name}: {count} accounts")
        
        if topic_counts:
            print("\nTop Topics:")
            for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  • {topic.title()}: {count} accounts")
        
        # Average confidence
        avg_confidence = sum(c.confidence_score for c in classifications) / len(classifications)
        print(f"\nAverage Confidence Score: {avg_confidence:.2f}")
    
    print(f"\n✅ Account classification test completed!")

if __name__ == "__main__":
    test_account_classification() 