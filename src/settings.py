from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Dict, Any
from pathlib import Path

class Settings(BaseSettings):
    """
    Centralized configuration for Twitter Tools.
    All settings can be overridden via environment variables or .env file.
    """
    
    # ==================== Twitter API Credentials ====================
    TWITTER_API_KEY: str
    TWITTER_API_SECRET: str
    TWITTER_ACCESS_TOKEN: str
    TWITTER_ACCESS_TOKEN_SECRET: str
    TWITTER_BEARER_TOKEN: str

    # ==================== Application Settings ====================
    # Database Configuration
    DATABASE_URL: str = 'sqlite:///./data/twittertools.db'
    CLASSIFICATIONS_DB_PATH: str = './theme_classifications.db'
    DATA_DIR: str = './data'
    
    # Server Configuration
    API_HOST: str = '127.0.0.1'
    API_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = 'INFO'
    
    # Frontend Configuration
    FRONTEND_URL: str = 'http://localhost:5173'
    CORS_ORIGINS: List[str] = [
        'http://localhost:5173',
        'http://localhost:5175', 
        'http://localhost:5176',
        'http://localhost:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:5175',
        'http://127.0.0.1:5176',
        'http://127.0.0.1:3000'
    ]
    
    # ==================== X API Configuration ====================
    X_API_BASE_URL: str = 'https://api.x.com/2'
    TWITTER_API_BASE_URL: str = 'https://api.twitter.com/2'
    
    # Rate Limiting Configuration
    RATE_LIMIT_WINDOW_MINUTES: int = 15
    DEFAULT_RATE_LIMIT_REQUESTS: int = 300
    RATE_LIMITS: Dict[str, Dict[str, int]] = {
        'tweets': {'requests': 300, 'max_results': 100},
        'likes': {'requests': 75, 'max_results': 100},
        'bookmarks': {'requests': 180, 'max_results': 500},
        'users_me': {'requests': 150},
        'list_members': {'requests': 75, 'max_results': 100}
    }
    
    # Request Configuration
    API_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 1
    
    # ==================== Caching Configuration ====================
    # Cache TTL Settings (in days)
    CACHE_TTL_STANDARD: int = 7
    CACHE_TTL_VOLATILE: int = 1  # hours for rapidly changing data
    CACHE_TTL_RELATIONSHIPS: int = 1  # days for follows/blocks/mutes
    CACHE_TTL_MEDIA: int = 30
    CACHE_TTL_PROFILES: int = 3
    
    # Cache Settings
    ENABLE_CACHING: bool = True
    CACHE_CLEANUP_INTERVAL_HOURS: int = 24
    MAX_CACHE_SIZE_MB: int = 1000
    
    # ==================== Semantic Classification ====================
    # Model Configuration
    SEMANTIC_MODEL_NAME: str = 'all-MiniLM-L6-v2'
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.3
    SEMANTIC_BATCH_SIZE: int = 32
    SEMANTIC_ENABLE_GPU: bool = False
    
    # Classification Settings
    CLASSIFICATION_CACHE_ENABLED: bool = True
    CLASSIFICATION_AUTO_UPDATE: bool = False
    MAX_CLASSIFICATION_WORKERS: int = 4
    
    # ==================== Topic Analysis ====================
    # Default Topic Filter Settings
    TOPIC_MIN_SCORE: float = 0.3
    TOPIC_MAX_RESULTS: int = 100
    TOPIC_SORT_BY: str = 'score'  # score, date, relevance
    
    # Topic Analysis Settings
    ENABLE_CUSTOM_TOPICS: bool = True
    TOPIC_ANALYSIS_BATCH_SIZE: int = 50
    
    # ==================== Data Processing ====================
    # Batch Processing Settings
    DEFAULT_BATCH_SIZE: int = 100
    MAX_BATCH_SIZE: int = 1000
    PROCESSING_TIMEOUT_MINUTES: int = 30
    
    # Data Validation
    VALIDATE_TWEET_TEXT: bool = True
    MAX_TWEET_LENGTH: int = 4000
    MIN_TWEET_LENGTH: int = 1
    
    # ==================== Security & Privacy ====================
    # Data Retention
    DATA_RETENTION_DAYS: int = 365
    AUTO_CLEANUP_ENABLED: bool = False
    HASH_CREDENTIALS: bool = True
    
    # Privacy Settings
    STORE_PERSONAL_DATA: bool = True
    ANONYMIZE_USERNAMES: bool = False
    GDPR_COMPLIANCE_MODE: bool = False
    
    # ==================== Performance & Monitoring ====================
    # Performance Settings
    ENABLE_PERFORMANCE_MONITORING: bool = True
    SLOW_QUERY_THRESHOLD_MS: int = 1000
    MEMORY_MONITORING_ENABLED: bool = True
    
    # Monitoring & Alerting
    ENABLE_HEALTH_CHECKS: bool = True
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60
    ALERT_ON_RATE_LIMIT: bool = True
    
    # ==================== Feature Flags ====================
    # Feature Toggles
    ENABLE_SEMANTIC_CLASSIFICATION: bool = True
    ENABLE_TOPIC_ANALYSIS: bool = True
    ENABLE_TWEET_ENRICHMENT: bool = True
    ENABLE_LIST_PROCESSING: bool = True
    ENABLE_PROFILE_ANALYSIS: bool = True
    
    # Experimental Features
    ENABLE_EXPERIMENTAL_FEATURES: bool = False
    ENABLE_REAL_TIME_PROCESSING: bool = False
    ENABLE_ADVANCED_ANALYTICS: bool = False
    
    # ==================== Development & Testing ====================
    # Development Settings
    ENABLE_DEV_MODE: bool = False
    MOCK_API_RESPONSES: bool = False
    DEV_USER_ID: str = ''
    
    # Testing Configuration
    TEST_MODE: bool = False
    TEST_DB_PATH: str = ':memory:'
    ENABLE_TEST_FIXTURES: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="allow",
        env_prefix="TWITTERTOOLS_"  # Optional: prefix for env vars
    )

@lru_cache
def get_settings():
    return Settings()

# Convenience functions for common configuration access
def get_db_path() -> Path:
    """Get the main database path as a Path object."""
    return Path(get_settings().DATA_DIR) / 'twittertools.db'

def get_classifications_db_path() -> Path:
    """Get the classifications database path as a Path object."""
    return Path(get_settings().CLASSIFICATIONS_DB_PATH)

def get_rate_limit_config(endpoint: str) -> Dict[str, int]:
    """Get rate limit configuration for a specific endpoint."""
    settings = get_settings()
    return settings.RATE_LIMITS.get(endpoint, {
        'requests': settings.DEFAULT_RATE_LIMIT_REQUESTS,
        'max_results': 100
    })

def is_feature_enabled(feature: str) -> bool:
    """Check if a specific feature is enabled."""
    settings = get_settings()
    feature_map = {
        'semantic_classification': settings.ENABLE_SEMANTIC_CLASSIFICATION,
        'topic_analysis': settings.ENABLE_TOPIC_ANALYSIS,
        'tweet_enrichment': settings.ENABLE_TWEET_ENRICHMENT,
        'list_processing': settings.ENABLE_LIST_PROCESSING,
        'profile_analysis': settings.ENABLE_PROFILE_ANALYSIS,
        'experimental': settings.ENABLE_EXPERIMENTAL_FEATURES,
        'real_time': settings.ENABLE_REAL_TIME_PROCESSING,
        'advanced_analytics': settings.ENABLE_ADVANCED_ANALYTICS,
    }
    return feature_map.get(feature, False) 