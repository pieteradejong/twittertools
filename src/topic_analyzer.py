"""
Modular Topic Analysis Service

Provides comprehensive topic analysis and filtering capabilities for any Twitter data.
Built on top of the existing SemanticTweetClassifier but designed for broader use cases.
"""

import logging
import sqlite3
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from pathlib import Path
import json
import numpy as np
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from .semantic_classifier import SemanticTweetClassifier
from .config import (
    TOPIC_MIN_SCORE, TOPIC_MAX_RESULTS, TOPIC_BATCH_SIZE,
    DATABASE_PATH, CLASSIFICATIONS_DB_PATH, SEMANTIC_SIMILARITY_THRESHOLD
)

logger = logging.getLogger(__name__)

class DataSource(Enum):
    """Supported data sources for topic analysis."""
    TWEETS = "tweets"
    LIKES = "likes"
    REPLIES = "replies"
    BOOKMARKS = "bookmarks"
    CUSTOM = "custom"

@dataclass
class TopicFilter:
    """Configuration for topic-based filtering."""
    topics: List[str]  # Topics to include (empty = all topics)
    min_score: float = TOPIC_MIN_SCORE  # Minimum similarity score
    max_results: int = TOPIC_MAX_RESULTS  # Maximum results to return
    sort_by: str = "score"  # "score", "date", "relevance"
    exclude_topics: List[str] = None  # Topics to exclude
    
    def __post_init__(self):
        if self.exclude_topics is None:
            self.exclude_topics = []

@dataclass
class TopicAnalysisResult:
    """Result of topic analysis operation."""
    item_id: str
    text: str
    topic_scores: Dict[str, float]
    assigned_topics: List[str]
    max_score: float
    data_source: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class TopicAnalyzer:
    """
    Modular topic analysis service for Twitter data.
    
    Features:
    - Works with any Twitter data type (tweets, likes, replies, etc.)
    - Configurable topic definitions
    - Advanced filtering and search capabilities
    - Batch processing for efficiency
    - Export capabilities for analysis
    """
    
    def __init__(self, similarity_threshold: float = SEMANTIC_SIMILARITY_THRESHOLD):
        """Initialize the topic analyzer."""
        self.classifier = SemanticTweetClassifier(similarity_threshold=similarity_threshold)
        self.db_path = Path(__file__).parent.parent / DATABASE_PATH.lstrip('./')
        self.classifications_db = Path(__file__).parent.parent / CLASSIFICATIONS_DB_PATH.lstrip('./')
        
    def add_custom_topic(self, topic_name: str, seed_phrases: List[str]) -> None:
        """Add a custom topic definition."""
        self.classifier.add_topic(topic_name, seed_phrases)
        logger.info(f"Added custom topic '{topic_name}' with {len(seed_phrases)} seed phrases")
    
    def get_available_topics(self) -> List[Dict[str, Any]]:
        """Get all available topics with statistics."""
        return self.classifier.get_available_topics()
    
    def analyze_data_source(self, 
                          data_source: DataSource, 
                          limit: Optional[int] = None,
                          custom_query: Optional[str] = None) -> List[TopicAnalysisResult]:
        """
        Analyze a specific data source for topics.
        
        Args:
            data_source: Type of data to analyze
            limit: Maximum number of items to analyze
            custom_query: Custom SQL query for data selection
            
        Returns:
            List of topic analysis results
        """
        # Get data based on source type
        if custom_query:
            data = self._execute_custom_query(custom_query, limit)
        else:
            data = self._get_data_by_source(data_source, limit)
        
        if not data:
            logger.warning(f"No data found for source: {data_source.value}")
            return []
        
        # Classify the data
        classifications = self.classifier.classify_tweets_batch(data)
        
        # Convert to TopicAnalysisResult objects
        results = []
        for classification in classifications:
            assigned_topics = [
                topic for topic, score in classification['all_scores'].items()
                if score >= self.classifier.similarity_threshold
            ]
            
            result = TopicAnalysisResult(
                item_id=classification['tweet_id'],
                text=classification['text'],
                topic_scores=classification['all_scores'],
                assigned_topics=assigned_topics,
                max_score=classification['max_score'],
                data_source=data_source.value,
                metadata={'classification_date': datetime.now().isoformat()}
            )
            results.append(result)
        
        # Save classifications
        self.classifier.save_classifications(classifications)
        
        return results
    
    def filter_by_topics(self, 
                        data_source: DataSource,
                        topic_filter: TopicFilter) -> List[Dict[str, Any]]:
        """
        Filter data by topic criteria.
        
        Args:
            data_source: Source of data to filter
            topic_filter: Filter configuration
            
        Returns:
            Filtered data with topic information
        """
        results = []
        
        # Build query based on filter criteria
        if topic_filter.topics:
            # Filter by specific topics
            for topic in topic_filter.topics:
                if topic in topic_filter.exclude_topics:
                    continue
                    
                topic_results = self.classifier.get_tweets_by_topic(
                    topic, 
                    topic_filter.min_score, 
                    topic_filter.max_results,
                    0
                )
                
                for result in topic_results:
                    result['data_source'] = data_source.value
                    result['filter_topic'] = topic
                    results.append(result)
        else:
            # Get all classified data above threshold
            results = self._get_all_classified_data(
                data_source, 
                topic_filter.min_score,
                topic_filter.max_results
            )
        
        # Apply exclusion filters
        if topic_filter.exclude_topics:
            results = [
                r for r in results 
                if not any(excluded in r.get('assigned_topics', []) 
                          for excluded in topic_filter.exclude_topics)
            ]
        
        # Sort results
        results = self._sort_results(results, topic_filter.sort_by)
        
        return results[:topic_filter.max_results]
    
    def semantic_search(self, 
                       query: str, 
                       data_source: DataSource = None,
                       limit: int = 20) -> List[Dict[str, Any]]:
        """
        Perform semantic search across data.
        
        Args:
            query: Natural language search query
            data_source: Specific data source to search (None = all)
            limit: Maximum results to return
            
        Returns:
            Search results with similarity scores
        """
        if data_source:
            # Search within specific data source
            return self.classifier.search_tweets_semantic(query, limit)
        else:
            # Search across all classified data
            return self._search_all_data(query, limit)
    
    def get_topic_distribution(self, data_source: DataSource = None) -> Dict[str, Any]:
        """
        Get topic distribution statistics.
        
        Args:
            data_source: Specific data source to analyze (None = all)
            
        Returns:
            Topic distribution with counts and percentages
        """
        with sqlite3.connect(self.classifications_db) as conn:
            if data_source:
                # This would require extending the classifications table to track data source
                # For now, return overall distribution
                pass
            
            cursor = conn.execute("""
                SELECT 
                    topic,
                    COUNT(*) as count,
                    AVG(score) as avg_score,
                    MAX(score) as max_score,
                    MIN(score) as min_score
                FROM classifications 
                WHERE score >= ?
                GROUP BY topic
                ORDER BY count DESC
            """, (self.classifier.similarity_threshold,))
            
            total_items = 0
            topics = []
            
            for row in cursor.fetchall():
                count = row[1]
                total_items += count
                topics.append({
                    'topic': row[0],
                    'count': count,
                    'avg_score': round(row[2], 3),
                    'max_score': round(row[3], 3),
                    'min_score': round(row[4], 3)
                })
            
            # Calculate percentages
            for topic in topics:
                topic['percentage'] = round((topic['count'] / total_items) * 100, 1) if total_items > 0 else 0
            
            return {
                'topics': topics,
                'total_items': total_items,
                'total_topics': len(topics),
                'threshold': self.classifier.similarity_threshold
            }
    
    def export_topic_analysis(self, 
                            data_source: DataSource,
                            output_format: str = "json") -> str:
        """
        Export topic analysis results.
        
        Args:
            data_source: Data source to export
            output_format: Export format ("json", "csv")
            
        Returns:
            Path to exported file
        """
        results = self.analyze_data_source(data_source)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"topic_analysis_{data_source.value}_{timestamp}"
        
        if output_format.lower() == "json":
            output_path = Path(f"{filename}.json")
            with open(output_path, 'w') as f:
                json.dump([
                    {
                        'item_id': r.item_id,
                        'text': r.text,
                        'topic_scores': r.topic_scores,
                        'assigned_topics': r.assigned_topics,
                        'max_score': r.max_score,
                        'data_source': r.data_source,
                        'metadata': r.metadata
                    } for r in results
                ], f, indent=2)
        elif output_format.lower() == "csv":
            import csv
            output_path = Path(f"{filename}.csv")
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['item_id', 'text', 'assigned_topics', 'max_score', 'data_source'])
                for r in results:
                    writer.writerow([
                        r.item_id,
                        r.text[:100] + "..." if len(r.text) > 100 else r.text,
                        ", ".join(r.assigned_topics),
                        r.max_score,
                        r.data_source
                    ])
        
        logger.info(f"Exported {len(results)} topic analysis results to {output_path}")
        return str(output_path)
    
    def _get_data_by_source(self, data_source: DataSource, limit: Optional[int]) -> List[Dict]:
        """Get data from specified source."""
        if data_source == DataSource.TWEETS:
            return self.classifier.get_tweets_from_db(limit)
        elif data_source == DataSource.LIKES:
            return self.classifier.get_likes_from_db(limit)
        elif data_source == DataSource.REPLIES:
            return self._get_replies_from_db(limit)
        elif data_source == DataSource.BOOKMARKS:
            return self._get_bookmarks_from_db(limit)
        else:
            logger.warning(f"Unsupported data source: {data_source}")
            return []
    
    def _get_replies_from_db(self, limit: Optional[int]) -> List[Dict]:
        """Get replies from database."""
        replies = []
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT id, text FROM tweets 
                WHERE text IS NOT NULL AND text != '' 
                AND in_reply_to_tweet_id IS NOT NULL
            """
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                replies.append({'id': row[0], 'text': row[1]})
        
        return replies
    
    def _get_bookmarks_from_db(self, limit: Optional[int]) -> List[Dict]:
        """Get bookmarks from database."""
        bookmarks = []
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT tweet_id, full_text FROM bookmarks 
                WHERE full_text IS NOT NULL AND full_text != ''
            """
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                bookmarks.append({'id': row[0], 'text': row[1]})
        
        return bookmarks
    
    def _execute_custom_query(self, query: str, limit: Optional[int]) -> List[Dict]:
        """Execute custom SQL query for data selection."""
        data = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                if limit and "LIMIT" not in query.upper():
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                for row in cursor.fetchall():
                    # Assume first column is ID, second is text
                    data.append({'id': row[0], 'text': row[1]})
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
        
        return data
    
    def _get_all_classified_data(self, 
                               data_source: DataSource, 
                               min_score: float,
                               limit: int) -> List[Dict]:
        """Get all classified data above threshold."""
        results = []
        with sqlite3.connect(self.classifications_db) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT tweet_id, full_text, topic, score
                FROM classifications 
                WHERE score >= ?
                ORDER BY score DESC
                LIMIT ?
            """, (min_score, limit))
            
            for row in cursor.fetchall():
                results.append({
                    'tweet_id': row[0],
                    'text': row[1],
                    'topic': row[2],
                    'score': row[3],
                    'data_source': data_source.value
                })
        
        return results
    
    def _search_all_data(self, query: str, limit: int) -> List[Dict]:
        """Search across all classified data."""
        # This uses the existing semantic search from the classifier
        return self.classifier.search_tweets_semantic(query, limit)
    
    def _sort_results(self, results: List[Dict], sort_by: str) -> List[Dict]:
        """Sort results by specified criteria."""
        if sort_by == "score":
            return sorted(results, key=lambda x: x.get('score', 0), reverse=True)
        elif sort_by == "date":
            # Would need date information in results
            return results
        elif sort_by == "relevance":
            # Could implement more sophisticated relevance scoring
            return sorted(results, key=lambda x: x.get('score', 0), reverse=True)
        else:
            return results

# Convenience functions for common use cases
def analyze_tweets_by_topic(topic: str, min_score: float = TOPIC_MIN_SCORE, limit: int = TOPIC_BATCH_SIZE) -> List[Dict]:
    """Quick function to analyze tweets by specific topic."""
    analyzer = TopicAnalyzer()
    topic_filter = TopicFilter(
        topics=[topic],
        min_score=min_score,
        max_results=limit
    )
    return analyzer.filter_by_topics(DataSource.TWEETS, topic_filter)

def analyze_likes_by_topic(topic: str, min_score: float = TOPIC_MIN_SCORE, limit: int = TOPIC_BATCH_SIZE) -> List[Dict]:
    """Quick function to analyze likes by specific topic."""
    analyzer = TopicAnalyzer()
    topic_filter = TopicFilter(
        topics=[topic],
        min_score=min_score,
        max_results=limit
    )
    return analyzer.filter_by_topics(DataSource.LIKES, topic_filter)

def get_topic_overview() -> Dict[str, Any]:
    """Get overview of all topics across all data."""
    analyzer = TopicAnalyzer()
    return analyzer.get_topic_distribution()

def search_content_semantically(query: str, limit: int = 20) -> List[Dict]:
    """Semantic search across all content."""
    analyzer = TopicAnalyzer()
    return analyzer.semantic_search(query, limit=limit) 