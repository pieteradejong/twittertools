"""
Account Classification Service

Classifies accounts you follow into meaningful lists based on:
1. Content analysis using existing semantic classification
2. Profile metadata (bio, location, verification status)
3. Engagement patterns (your interactions with their content)
4. Social graph analysis (mutual connections)

Built on top of the existing SemanticTweetClassifier and TopicAnalyzer.
"""

import logging
import sqlite3
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from pathlib import Path
import json
import numpy as np
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter

from .semantic_classifier import SemanticTweetClassifier
from .topic_analyzer import TopicAnalyzer, DataSource
from .config import (
    DATABASE_PATH, CLASSIFICATIONS_DB_PATH, SEMANTIC_SIMILARITY_THRESHOLD,
    DEFAULT_TOPICS
)

logger = logging.getLogger(__name__)

@dataclass
class AccountClassification:
    """Result of account classification."""
    user_id: str
    username: str
    display_name: str
    primary_topics: List[str]
    topic_scores: Dict[str, float]
    profile_category: str
    engagement_score: float
    suggested_lists: List[str]
    confidence_score: float
    classification_reasons: List[str]

@dataclass
class ListSuggestion:
    """Suggested list with members."""
    list_name: str
    description: str
    members: List[Dict[str, Any]]
    category: str
    confidence_score: float
    creation_reason: str

class ClassificationMethod(Enum):
    """Available classification methods."""
    CONTENT_BASED = "content"
    PROFILE_BASED = "profile"
    ENGAGEMENT_BASED = "engagement"
    HYBRID = "hybrid"

class AccountClassifier:
    """
    Comprehensive account classification service.
    
    Features:
    - Content-based classification using semantic analysis
    - Profile-based classification using bio and metadata
    - Engagement-based classification using interaction patterns
    - Hybrid approach combining multiple signals
    - Automatic list suggestions with confidence scores
    """
    
    def __init__(self, similarity_threshold: float = SEMANTIC_SIMILARITY_THRESHOLD):
        """Initialize the account classifier."""
        self.semantic_classifier = SemanticTweetClassifier(similarity_threshold=similarity_threshold)
        self.topic_analyzer = TopicAnalyzer(similarity_threshold=similarity_threshold)
        self.db_path = Path(__file__).parent.parent / 'data' / 'x_data.db'
        self.classifications_db = Path(__file__).parent.parent / CLASSIFICATIONS_DB_PATH.lstrip('./')
        
        # Profile-based classification patterns
        self.profile_patterns = self._get_profile_patterns()
        
    def _get_profile_patterns(self) -> Dict[str, List[str]]:
        """Define patterns for profile-based classification."""
        return {
            'tech_professional': [
                'software engineer', 'developer', 'programmer', 'cto', 'ceo tech',
                'startup founder', 'product manager', 'data scientist', 'ml engineer',
                'devops', 'full stack', 'frontend', 'backend', 'mobile developer'
            ],
            'investor_vc': [
                'venture capital', 'investor', 'partner at', 'managing director',
                'angel investor', 'fund', 'investment', 'portfolio', 'vc'
            ],
            'journalist_media': [
                'journalist', 'reporter', 'editor', 'writer', 'correspondent',
                'news', 'media', 'columnist', 'author', 'blogger'
            ],
            'academic_researcher': [
                'professor', 'phd', 'researcher', 'university', 'academic',
                'postdoc', 'faculty', 'scholar', 'scientist'
            ],
            'crypto_web3': [
                'crypto', 'blockchain', 'web3', 'defi', 'nft', 'ethereum',
                'bitcoin', 'solana', 'polygon', 'dao'
            ],
            'designer_creative': [
                'designer', 'ux', 'ui', 'creative', 'artist', 'illustrator',
                'brand designer', 'product designer', 'graphic designer'
            ],
            'marketing_growth': [
                'marketing', 'growth', 'seo', 'content marketing', 'digital marketing',
                'brand manager', 'community manager', 'social media'
            ]
        }
    
    def classify_account(self, 
                        user_id: str, 
                        method: ClassificationMethod = ClassificationMethod.HYBRID,
                        content_sample_size: int = 50) -> AccountClassification:
        """
        Classify a single account using the specified method.
        
        Args:
            user_id: Account ID to classify
            method: Classification method to use
            content_sample_size: Number of recent tweets to analyze for content-based classification
            
        Returns:
            AccountClassification with results and confidence scores
        """
        # Get account info
        account_info = self._get_account_info(user_id)
        if not account_info:
            raise ValueError(f"Account {user_id} not found")
        
        classification_reasons = []
        topic_scores = {}
        primary_topics = []
        profile_category = "unknown"
        engagement_score = 0.0
        
        if method in [ClassificationMethod.CONTENT_BASED, ClassificationMethod.HYBRID]:
            # Content-based classification
            content_results = self._classify_by_content(user_id, content_sample_size)
            topic_scores.update(content_results['topic_scores'])
            primary_topics.extend(content_results['primary_topics'])
            classification_reasons.extend(content_results['reasons'])
        
        if method in [ClassificationMethod.PROFILE_BASED, ClassificationMethod.HYBRID]:
            # Profile-based classification
            profile_results = self._classify_by_profile(account_info)
            profile_category = profile_results['category']
            classification_reasons.extend(profile_results['reasons'])
        
        if method in [ClassificationMethod.ENGAGEMENT_BASED, ClassificationMethod.HYBRID]:
            # Engagement-based classification
            engagement_results = self._classify_by_engagement(user_id)
            engagement_score = engagement_results['score']
            classification_reasons.extend(engagement_results['reasons'])
        
        # Generate list suggestions
        suggested_lists = self._suggest_lists_for_account(
            primary_topics, profile_category, engagement_score
        )
        
        # Calculate overall confidence
        confidence_score = self._calculate_confidence(
            topic_scores, profile_category, engagement_score, method
        )
        
        return AccountClassification(
            user_id=user_id,
            username=account_info['username'] or f"user_{user_id[-8:]}",
            display_name=account_info['display_name'] or f"User {user_id[-8:]}",
            primary_topics=primary_topics,
            topic_scores=topic_scores,
            profile_category=profile_category,
            engagement_score=engagement_score,
            suggested_lists=suggested_lists,
            confidence_score=confidence_score,
            classification_reasons=classification_reasons
        )
    
    def classify_all_following(self, 
                             method: ClassificationMethod = ClassificationMethod.HYBRID,
                             limit: Optional[int] = None) -> List[AccountClassification]:
        """
        Classify all accounts you're following.
        
        Args:
            method: Classification method to use
            limit: Maximum number of accounts to classify (None = all)
            
        Returns:
            List of AccountClassification results
        """
        following_accounts = self._get_following_accounts(limit)
        logger.info(f"Classifying {len(following_accounts)} accounts using {method.value} method")
        
        results = []
        for i, account in enumerate(following_accounts):
            try:
                classification = self.classify_account(account['id'], method)
                results.append(classification)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Classified {i + 1}/{len(following_accounts)} accounts")
                    
            except Exception as e:
                logger.error(f"Error classifying account {account['id']}: {e}")
                continue
        
        logger.info(f"Successfully classified {len(results)} accounts")
        return results
    
    def suggest_lists(self, 
                     classifications: List[AccountClassification],
                     min_members_per_list: int = 3,
                     max_lists: int = 20) -> List[ListSuggestion]:
        """
        Generate list suggestions based on account classifications.
        
        Args:
            classifications: List of account classifications
            min_members_per_list: Minimum accounts required to suggest a list
            max_lists: Maximum number of lists to suggest
            
        Returns:
            List of suggested lists with members
        """
        # Group accounts by various criteria
        topic_groups = defaultdict(list)
        profile_groups = defaultdict(list)
        hybrid_groups = defaultdict(list)
        
        for classification in classifications:
            # Group by primary topics
            for topic in classification.primary_topics:
                topic_groups[topic].append(classification)
            
            # Group by profile category
            if classification.profile_category != "unknown":
                profile_groups[classification.profile_category].append(classification)
            
            # Create hybrid groups (topic + profile)
            for topic in classification.primary_topics:
                if classification.profile_category != "unknown":
                    hybrid_key = f"{topic}_{classification.profile_category}"
                    hybrid_groups[hybrid_key].append(classification)
        
        suggestions = []
        
        # Topic-based lists
        for topic, members in topic_groups.items():
            if len(members) >= min_members_per_list:
                suggestions.append(ListSuggestion(
                    list_name=f"{topic.title()} Accounts",
                    description=f"Accounts that frequently post about {topic}",
                    members=[self._classification_to_member(m) for m in members],
                    category="topic",
                    confidence_score=np.mean([m.confidence_score for m in members]),
                    creation_reason=f"Content analysis identified {len(members)} accounts with {topic} focus"
                ))
        
        # Profile-based lists
        for category, members in profile_groups.items():
            if len(members) >= min_members_per_list:
                suggestions.append(ListSuggestion(
                    list_name=self._format_profile_category(category),
                    description=f"Accounts identified as {category.replace('_', ' ')}",
                    members=[self._classification_to_member(m) for m in members],
                    category="profile",
                    confidence_score=np.mean([m.confidence_score for m in members]),
                    creation_reason=f"Profile analysis identified {len(members)} {category.replace('_', ' ')} accounts"
                ))
        
        # High-engagement lists
        high_engagement = [c for c in classifications if c.engagement_score > 0.7]
        if len(high_engagement) >= min_members_per_list:
            suggestions.append(ListSuggestion(
                list_name="High Engagement",
                description="Accounts you frequently interact with",
                members=[self._classification_to_member(m) for m in high_engagement],
                category="engagement",
                confidence_score=np.mean([m.confidence_score for m in high_engagement]),
                creation_reason=f"Engagement analysis identified {len(high_engagement)} highly-engaged accounts"
            ))
        
        # Sort by confidence and limit
        suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
        return suggestions[:max_lists]
    
    def _classify_by_content(self, user_id: str, sample_size: int) -> Dict[str, Any]:
        """Classify account based on their content using semantic analysis."""
        # Get recent tweets from this user (if available in our data)
        user_content = self._get_user_content(user_id, sample_size)
        
        if not user_content:
            return {
                'topic_scores': {},
                'primary_topics': [],
                'reasons': ["No content available for analysis"]
            }
        
        # Classify their content
        classifications = self.semantic_classifier.classify_tweets_batch(user_content)
        
        # Aggregate topic scores
        topic_totals = defaultdict(float)
        topic_counts = defaultdict(int)
        
        for classification in classifications:
            for topic, score in classification['all_scores'].items():
                if score >= self.semantic_classifier.similarity_threshold:
                    topic_totals[topic] += score
                    topic_counts[topic] += 1
        
        # Calculate average scores
        topic_scores = {}
        for topic in topic_totals:
            topic_scores[topic] = topic_totals[topic] / topic_counts[topic]
        
        # Get primary topics (top 3)
        primary_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        primary_topics = [topic for topic, score in primary_topics]
        
        reasons = [
            f"Analyzed {len(user_content)} pieces of content",
            f"Found {len(topic_scores)} relevant topics",
            f"Primary topics: {', '.join(primary_topics[:2])}"
        ]
        
        return {
            'topic_scores': topic_scores,
            'primary_topics': primary_topics,
            'reasons': reasons
        }
    
    def _classify_by_profile(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Classify account based on profile information."""
        bio = account_info.get('bio', '') or ''
        bio = bio.lower()
        location = account_info.get('location', '') or ''
        location = location.lower()
        
        category_scores = {}
        reasons = []
        
        # Check bio against patterns
        for category, patterns in self.profile_patterns.items():
            score = 0
            matched_patterns = []
            
            for pattern in patterns:
                if pattern.lower() in bio:
                    score += 1
                    matched_patterns.append(pattern)
            
            if score > 0:
                category_scores[category] = score / len(patterns)
                reasons.append(f"Bio matches {category}: {', '.join(matched_patterns[:2])}")
        
        # Determine primary category
        if category_scores:
            primary_category = max(category_scores.items(), key=lambda x: x[1])[0]
        else:
            primary_category = "unknown"
            reasons.append("No clear profile category identified")
        
        return {
            'category': primary_category,
            'scores': category_scores,
            'reasons': reasons
        }
    
    def _classify_by_engagement(self, user_id: str) -> Dict[str, Any]:
        """Classify account based on your engagement patterns with them."""
        # This would analyze:
        # - How often you like their tweets
        # - How often you retweet them
        # - How often you reply to them
        # - Recency of interactions
        
        # For now, return placeholder - would need to implement engagement tracking
        return {
            'score': 0.5,  # Placeholder
            'reasons': ["Engagement analysis not yet implemented"]
        }
    
    def _suggest_lists_for_account(self, 
                                 primary_topics: List[str], 
                                 profile_category: str, 
                                 engagement_score: float) -> List[str]:
        """Generate list suggestions for a single account."""
        suggestions = []
        
        # Topic-based suggestions
        for topic in primary_topics:
            suggestions.append(f"{topic.title()} Accounts")
        
        # Profile-based suggestions
        if profile_category != "unknown":
            suggestions.append(self._format_profile_category(profile_category))
        
        # Engagement-based suggestions
        if engagement_score > 0.7:
            suggestions.append("High Engagement")
        elif engagement_score > 0.4:
            suggestions.append("Regular Interactions")
        
        return list(set(suggestions))  # Remove duplicates
    
    def _calculate_confidence(self, 
                            topic_scores: Dict[str, float], 
                            profile_category: str, 
                            engagement_score: float,
                            method: ClassificationMethod) -> float:
        """Calculate overall confidence score for classification."""
        confidence_factors = []
        
        # Content confidence
        if topic_scores:
            max_topic_score = max(topic_scores.values())
            confidence_factors.append(max_topic_score)
        
        # Profile confidence
        if profile_category != "unknown":
            confidence_factors.append(0.8)  # High confidence for profile matches
        
        # Engagement confidence
        if engagement_score > 0:
            confidence_factors.append(engagement_score)
        
        if not confidence_factors:
            return 0.1  # Very low confidence
        
        return np.mean(confidence_factors)
    
    def _get_account_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get account information from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, username, display_name, bio, location, verified, 
                       follower_count, following_count, avatar_url
                FROM users 
                WHERE id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'username': row[1],
                    'display_name': row[2],
                    'bio': row[3],
                    'location': row[4],
                    'verified': row[5],
                    'follower_count': row[6],
                    'following_count': row[7],
                    'avatar_url': row[8]
                }
        return None
    
    def _get_following_accounts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get list of accounts you're following."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current user ID
            cursor = conn.execute("SELECT account_id FROM account LIMIT 1")
            user_row = cursor.fetchone()
            if not user_row:
                return []
            
            user_id = user_row[0]
            
            # Get following relationships
            query = """
                SELECT r.target_user_id, u.username, u.display_name
                FROM relationships r
                LEFT JOIN users u ON r.target_user_id = u.id
                WHERE r.source_user_id = ? AND r.relationship_type = 'following'
                ORDER BY u.display_name
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query, (user_id,))
            
            accounts = []
            for row in cursor.fetchall():
                accounts.append({
                    'id': row[0],
                    'username': row[1],
                    'display_name': row[2]
                })
            
            return accounts
    
    def _get_user_content(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get content from a specific user for analysis."""
        # This would need to be implemented based on available data
        # For now, return empty list as we may not have individual user tweets
        return []
    
    def _classification_to_member(self, classification: AccountClassification) -> Dict[str, Any]:
        """Convert AccountClassification to list member format."""
        return {
            'id': classification.user_id,
            'username': classification.username,
            'display_name': classification.display_name,
            'primary_topics': classification.primary_topics,
            'profile_category': classification.profile_category,
            'confidence_score': classification.confidence_score
        }
    
    def _format_profile_category(self, category: str) -> str:
        """Format profile category for list name."""
        category_names = {
            'tech_professional': 'Tech Professionals',
            'investor_vc': 'Investors & VCs',
            'journalist_media': 'Journalists & Media',
            'academic_researcher': 'Academics & Researchers',
            'crypto_web3': 'Crypto & Web3',
            'designer_creative': 'Designers & Creatives',
            'marketing_growth': 'Marketing & Growth'
        }
        return category_names.get(category, category.replace('_', ' ').title())

# Utility functions for quick analysis
def classify_following_accounts(method: ClassificationMethod = ClassificationMethod.HYBRID, 
                              limit: Optional[int] = None) -> List[AccountClassification]:
    """Quick function to classify all following accounts."""
    classifier = AccountClassifier()
    return classifier.classify_all_following(method, limit)

def suggest_lists_for_following(min_members: int = 3, max_lists: int = 15) -> List[ListSuggestion]:
    """Quick function to get list suggestions for following accounts."""
    classifier = AccountClassifier()
    classifications = classifier.classify_all_following()
    return classifier.suggest_lists(classifications, min_members, max_lists) 