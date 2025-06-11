"""
Semantic Tweet Classification Service

Uses pre-trained sentence transformers to classify tweets into topics
based on semantic similarity to seed phrases. Supports multi-label
classification with configurable thresholds.
"""

import logging
import sqlite3
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import time
from .config import (
    SEMANTIC_MODEL_NAME, SEMANTIC_SIMILARITY_THRESHOLD, SEMANTIC_BATCH_SIZE,
    CLASSIFICATIONS_DB_PATH, DATABASE_PATH, DEFAULT_TOPICS
)

logger = logging.getLogger(__name__)

class SemanticTweetClassifier:
    """
    Semantic tweet classifier using sentence transformers and cosine similarity.
    
    Features:
    - Zero-shot classification (no labeled data needed)
    - Multi-label support (tweets can have multiple topics)
    - Extensible topic definitions via seed phrases
    - Configurable similarity thresholds
    - Batch processing for efficiency
    """
    
    def __init__(self, model_name: str = SEMANTIC_MODEL_NAME, similarity_threshold: float = SEMANTIC_SIMILARITY_THRESHOLD):
        """
        Initialize the semantic classifier.
        
        Args:
            model_name: Sentence transformer model name
            similarity_threshold: Minimum cosine similarity for topic assignment
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.model = None
        self.topic_embeddings = {}
        self.topic_definitions = self._get_default_topics()
        
        # Database paths
        self.db_path = Path(__file__).parent.parent / DATABASE_PATH.lstrip('./')
        self.classifications_db = Path(__file__).parent.parent / CLASSIFICATIONS_DB_PATH.lstrip('./')
        
    def _get_default_topics(self) -> Dict[str, List[str]]:
        """
        Define topics with seed phrases for semantic matching.
        
        Each topic has multiple seed phrases that capture different aspects
        of the topic. The classifier will compute similarity to all phrases
        and use the maximum similarity score.
        """
        return DEFAULT_TOPICS
    
    def load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully")
    
    def _compute_topic_embeddings(self):
        """Pre-compute embeddings for all topic seed phrases."""
        if not self.topic_embeddings:
            logger.info("Computing topic embeddings...")
            self.load_model()
            
            for topic, phrases in self.topic_definitions.items():
                # Compute embeddings for all seed phrases
                embeddings = self.model.encode(phrases)
                self.topic_embeddings[topic] = embeddings
                logger.info(f"Computed embeddings for topic '{topic}' ({len(phrases)} phrases)")
    
    def classify_text(self, text: str) -> Dict[str, float]:
        """
        Classify a single text into topics with confidence scores.
        
        Args:
            text: Text to classify
            
        Returns:
            Dictionary mapping topic names to similarity scores
        """
        self.load_model()
        self._compute_topic_embeddings()
        
        # Encode the input text
        text_embedding = self.model.encode([text])
        
        topic_scores = {}
        
        for topic, topic_embeddings in self.topic_embeddings.items():
            # Compute similarity to all seed phrases for this topic
            similarities = cosine_similarity(text_embedding, topic_embeddings)[0]
            
            # Use maximum similarity across all seed phrases
            max_similarity = float(np.max(similarities))
            topic_scores[topic] = max_similarity
        
        return topic_scores
    
    def classify_tweets_batch(self, tweets: List[Dict], batch_size: int = SEMANTIC_BATCH_SIZE) -> List[Dict]:
        """
        Classify multiple tweets efficiently using batch processing.
        
        Args:
            tweets: List of tweet dictionaries with 'id' and 'text' keys
            batch_size: Number of tweets to process at once
            
        Returns:
            List of classification results with tweet_id, topics, and scores
        """
        self.load_model()
        self._compute_topic_embeddings()
        
        results = []
        total_tweets = len(tweets)
        
        logger.info(f"Classifying {total_tweets} tweets in batches of {batch_size}")
        
        for i in range(0, total_tweets, batch_size):
            batch = tweets[i:i + batch_size]
            batch_texts = [tweet['text'] for tweet in batch]
            
            # Encode batch of texts
            text_embeddings = self.model.encode(batch_texts)
            
            # Classify each text in the batch
            for j, tweet in enumerate(batch):
                text_embedding = text_embeddings[j:j+1]
                topic_scores = {}
                
                for topic, topic_embeddings in self.topic_embeddings.items():
                    similarities = cosine_similarity(text_embedding, topic_embeddings)[0]
                    max_similarity = float(np.max(similarities))
                    topic_scores[topic] = max_similarity
                
                # Filter topics above threshold
                assigned_topics = {
                    topic: score for topic, score in topic_scores.items()
                    if score >= self.similarity_threshold
                }
                
                results.append({
                    'tweet_id': tweet['id'],
                    'text': tweet['text'],
                    'all_scores': topic_scores,
                    'assigned_topics': assigned_topics,
                    'max_score': max(topic_scores.values()) if topic_scores else 0.0
                })
            
            if (i + batch_size) % (batch_size * 10) == 0:
                logger.info(f"Processed {min(i + batch_size, total_tweets)}/{total_tweets} tweets")
        
        logger.info(f"Classification complete. {len(results)} tweets processed.")
        return results
    
    def get_tweets_from_db(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch tweets from the database for classification."""
        tweets = []
        
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT id, text FROM tweets WHERE text IS NOT NULL AND text != ''"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                tweets.append({
                    'id': row[0],
                    'text': row[1]
                })
        
        logger.info(f"Fetched {len(tweets)} tweets from database")
        return tweets
    
    def get_likes_from_db(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch likes from the database for classification."""
        likes = []
        
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT tweet_id, full_text FROM likes WHERE full_text IS NOT NULL AND full_text != ''"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                likes.append({
                    'id': row[0],
                    'text': row[1]
                })
        
        logger.info(f"Fetched {len(likes)} likes from database")
        return likes
    
    def save_classifications(self, classifications: List[Dict]):
        """Save classification results to the theme_classifications database."""
        with sqlite3.connect(self.classifications_db) as conn:
            # Create updated schema if needed
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classifications (
                    tweet_id TEXT,
                    full_text TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    score REAL NOT NULL,
                    classification_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tweet_id, topic)
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tweet_id ON classifications (tweet_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON classifications (topic)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON classifications (score)")
            
            # Insert classifications
            for result in classifications:
                tweet_id = result['tweet_id']
                text = result['text']
                
                # Insert all topic scores (not just assigned ones)
                for topic, score in result['all_scores'].items():
                    conn.execute("""
                        INSERT OR REPLACE INTO classifications 
                        (tweet_id, full_text, topic, score) 
                        VALUES (?, ?, ?, ?)
                    """, (tweet_id, text, topic, score))
            
            conn.commit()
        
        logger.info(f"Saved {len(classifications)} tweet classifications to database")
    
    def get_tweets_by_topic(self, topic: str, min_score: float = None, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Retrieve tweets classified under a specific topic."""
        if min_score is None:
            min_score = self.similarity_threshold
        
        with sqlite3.connect(self.classifications_db) as conn:
            cursor = conn.execute("""
                SELECT tweet_id, full_text, score 
                FROM classifications 
                WHERE topic = ? AND score >= ?
                ORDER BY score DESC
                LIMIT ? OFFSET ?
            """, (topic, min_score, limit, offset))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'tweet_id': row[0],
                    'text': row[1],
                    'score': row[2],
                    'topic': topic
                })
            
            return results
    
    def get_available_topics(self) -> List[Dict[str, any]]:
        """Get all available topics with their tweet counts."""
        with sqlite3.connect(self.classifications_db) as conn:
            cursor = conn.execute("""
                SELECT topic, COUNT(*) as count, AVG(score) as avg_score, MAX(score) as max_score
                FROM classifications 
                WHERE score >= ?
                GROUP BY topic
                ORDER BY count DESC
            """, (self.similarity_threshold,))
            
            topics = []
            for row in cursor.fetchall():
                topics.append({
                    'topic': row[0],
                    'count': row[1],
                    'avg_score': round(row[2], 3),
                    'max_score': round(row[3], 3)
                })
            
            return topics
    
    def search_tweets_semantic(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search tweets using semantic similarity to a query.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            
        Returns:
            List of tweets with similarity scores
        """
        self.load_model()
        
        # Get all classified tweets
        with sqlite3.connect(self.classifications_db) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT tweet_id, full_text 
                FROM classifications
            """)
            
            tweets = [(row[0], row[1]) for row in cursor.fetchall()]
        
        if not tweets:
            return []
        
        # Encode query and tweet texts
        query_embedding = self.model.encode([query])
        tweet_texts = [tweet[1] for tweet in tweets]
        tweet_embeddings = self.model.encode(tweet_texts)
        
        # Compute similarities
        similarities = cosine_similarity(query_embedding, tweet_embeddings)[0]
        
        # Sort by similarity and return top results
        tweet_scores = list(zip(tweets, similarities))
        tweet_scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for (tweet_id, text), score in tweet_scores[:limit]:
            if score >= 0.2:  # Minimum similarity threshold for search
                results.append({
                    'tweet_id': tweet_id,
                    'text': text,
                    'similarity_score': float(score)
                })
        
        return results

    def add_topic(self, topic_name: str, seed_phrases: List[str]):
        """Add a new topic with seed phrases."""
        self.topic_definitions[topic_name] = seed_phrases
        # Clear cached embeddings to force recomputation
        if topic_name in self.topic_embeddings:
            del self.topic_embeddings[topic_name]
        logger.info(f"Added new topic '{topic_name}' with {len(seed_phrases)} seed phrases")
    
    def update_similarity_threshold(self, threshold: float):
        """Update the similarity threshold for topic assignment."""
        self.similarity_threshold = threshold
        logger.info(f"Updated similarity threshold to {threshold}")


def classify_all_tweets():
    """Utility function to classify all tweets in the database."""
    from .config import SEMANTIC_SIMILARITY_THRESHOLD_LOW
    classifier = SemanticTweetClassifier(similarity_threshold=SEMANTIC_SIMILARITY_THRESHOLD_LOW)
    
    # Get tweets from database
    tweets = classifier.get_tweets_from_db()
    
    if not tweets:
        logger.warning("No tweets found in database")
        return
    
    # Classify tweets
    start_time = time.time()
    classifications = classifier.classify_tweets_batch(tweets, batch_size=SEMANTIC_BATCH_SIZE)
    end_time = time.time()
    
    # Save results
    classifier.save_classifications(classifications)
    
    # Print summary
    total_time = end_time - start_time
    logger.info(f"Classification completed in {total_time:.2f} seconds")
    logger.info(f"Average time per tweet: {(total_time / len(tweets)):.3f} seconds")
    
    # Show topic distribution
    topics = classifier.get_available_topics()
    logger.info("Topic distribution:")
    for topic_info in topics:
        logger.info(f"  {topic_info['topic']}: {topic_info['count']} tweets (avg score: {topic_info['avg_score']})")


def classify_all_likes():
    """Utility function to classify all likes in the database."""
    from .config import SEMANTIC_SIMILARITY_THRESHOLD_LOW
    classifier = SemanticTweetClassifier(similarity_threshold=SEMANTIC_SIMILARITY_THRESHOLD_LOW)
    
    # Get likes from database
    likes = classifier.get_likes_from_db()
    
    if not likes:
        logger.warning("No likes found in database")
        return
    
    # Classify likes
    start_time = time.time()
    classifications = classifier.classify_tweets_batch(likes, batch_size=SEMANTIC_BATCH_SIZE)
    end_time = time.time()
    
    # Save results
    classifier.save_classifications(classifications)
    
    # Print summary
    total_time = end_time - start_time
    logger.info(f"Like classification completed in {total_time:.2f} seconds")
    logger.info(f"Average time per like: {(total_time / len(likes)):.3f} seconds")
    
    # Show topic distribution
    topics = classifier.get_available_topics()
    logger.info("Topic distribution for likes:")
    for topic_info in topics:
        logger.info(f"  {topic_info['topic']}: {topic_info['count']} items (avg score: {topic_info['avg_score']})")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    print("Classifying all tweets and likes...")
    classify_all_tweets()
    classify_all_likes() 