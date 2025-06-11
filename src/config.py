"""
Centralized Configuration for Twitter Tools

Simple constants file for easy configuration management.
Import these variables anywhere you need configuration values.
"""

# ==================== Database Configuration ====================
DATABASE_PATH = './data/twittertools.db'
CLASSIFICATIONS_DB_PATH = './theme_classifications.db'
DATA_DIR = './data'

# ==================== API Configuration ====================
API_HOST = '127.0.0.1'
API_PORT = 8000
API_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

# ==================== Twitter/X API URLs ====================
TWITTER_API_BASE_URL = 'https://api.twitter.com/2'
X_API_BASE_URL = 'https://api.x.com/2'

# ==================== Rate Limiting ====================
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_WINDOW_SECONDS = 15 * 60  # 15 minutes in seconds
DEFAULT_MAX_RESULTS = 100
RATE_LIMITS = {
    'tweets': {'requests': 300, 'max_results': 100},
    'likes': {'requests': 75, 'max_results': 100},
    'bookmarks': {'requests': 180, 'max_results': 500},
    'users_me': {'requests': 150},
    'list_members': {'requests': 75, 'max_results': 100}
}

# ==================== Caching Configuration ====================
CACHE_TTL_DAYS = 7
CACHE_TTL_HOURS = 24
CACHE_TTL_PROFILES = 3  # days
CACHE_TTL_LISTS = 7  # days  
ENABLE_CACHING = True

# ==================== Semantic Classification ====================
SEMANTIC_MODEL_NAME = 'all-MiniLM-L6-v2'
SEMANTIC_SIMILARITY_THRESHOLD = 0.3
SEMANTIC_SIMILARITY_THRESHOLD_LOW = 0.25  # For broader matching
SEMANTIC_BATCH_SIZE = 32
SEMANTIC_CLASSIFICATION_BATCH_SIZE = 5  # For testing

# ==================== Topic Analysis ====================
TOPIC_MIN_SCORE = 0.3
TOPIC_MAX_RESULTS = 100
TOPIC_BATCH_SIZE = 50

# ==================== Batch Processing ====================
DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 1000
USER_PROFILE_BATCH_SIZE = 100  # For profile enrichment
API_CALL_PAUSE_INTERVAL = 10  # Pause every N API calls
API_CALL_PAUSE_SECONDS = 1  # Sleep duration between batches

# ==================== API Limits & Defaults ====================
# Query/Result Limits
MIN_TWEETS_FOR_TEST = 5
DEFAULT_LIKES_LIMIT = 20
DEFAULT_TWEETS_LIMIT = 20
DEFAULT_FOLLOWING_LIMIT = 100
DEFAULT_FOLLOWERS_LIMIT = 100
DEFAULT_LISTS_LIMIT = 100
DEFAULT_BOOKMARKS_LIMIT = 20

# API Endpoint Limits
MAX_TWEETS_PER_REQUEST = 100
MAX_LIKES_PER_REQUEST = 100
MAX_BOOKMARKS_PER_REQUEST = 100
MAX_FOLLOWERS_PER_REQUEST = 1000
MAX_FOLLOWING_PER_REQUEST = 1000
MAX_LISTS_PER_REQUEST = 100
MAX_SPACES_PER_REQUEST = 100
MAX_DM_PER_REQUEST = 100
MAX_COMMUNITIES_PER_REQUEST = 100
SEARCH_TWEETS_RECENT_MAX = 100
SEARCH_TWEETS_ALL_MAX = 500

# ==================== Frontend Configuration ====================
FRONTEND_URL = 'http://localhost:5173'
CORS_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:5175',
    'http://localhost:5176',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5175',
    'http://127.0.0.1:5176',
    'http://127.0.0.1:3000'
]

# ==================== Enrichment & Processing ====================
# Profile Enrichment
PROFILE_ENRICHMENT_DEFAULT_LIMIT = 50
PROFILE_ENRICHMENT_MAX_LIMIT = 100

# List Enrichment  
LIST_ENRICHMENT_DEFAULT_LIMIT = 10
LIST_ENRICHMENT_MAX_LIMIT = 50
LIST_ENRICHMENT_DEFAULT_DELAY = 1.0  # seconds
LIST_ENRICHMENT_MIN_DELAY = 0.5
LIST_ENRICHMENT_MAX_DELAY = 5.0

# Tweet Enrichment
TWEET_ENRICHMENT_DEFAULT_LIMIT = 100
TWEET_ENRICHMENT_CACHE_TTL_DAYS = 30

# ==================== Performance & Monitoring ====================
# Retry Configuration
RETRY_EXPONENTIAL_MIN_WAIT = 60  # seconds
RETRY_EXPONENTIAL_MAX_WAIT = 900  # 15 minutes
RETRY_MAX_ATTEMPTS = 3

# Performance Thresholds
SLOW_QUERY_THRESHOLD_MS = 1000
MEMORY_MONITORING_ENABLED = True

# ==================== UI/UX Configuration ====================
# Pagination
DEFAULT_PAGINATION_LIMIT = 20
MAX_PAGINATION_LIMIT = 100

# Text Display
MAX_TWEET_DISPLAY_LENGTH = 100  # characters to show before truncation
TRUNCATION_SUFFIX = "..."

# Batch Size Options (for UI dropdowns)
BATCH_SIZE_OPTIONS = [10, 25, 50, 100]

# ==================== Testing Configuration ====================
TEST_SIMILARITY_THRESHOLD = 0.25
TEST_LIKES_LIMIT = 10
TEST_TWEETS_LIMIT = 3
TEST_BATCH_SIZE = 5
TEST_USER_REPLIES_LIMIT = 50

# ==================== Zero Engagement Thresholds ====================
ZERO_ENGAGEMENT_FAVORITE_COUNT = 0
ZERO_ENGAGEMENT_RETWEET_COUNT = 0

# ==================== Topic Classification ====================
# Default topics for semantic classification
DEFAULT_TOPICS = {
    'technology': [
        'artificial intelligence and machine learning',
        'software development and programming',
        'tech startups and innovation',
        'blockchain and cryptocurrency',
        'data science and analytics'
    ],
    'politics': [
        'political news and elections',
        'government policy and legislation',
        'political commentary and opinion',
        'voting and democracy',
        'political parties and candidates'
    ],
    'business': [
        'entrepreneurship and business strategy',
        'finance and investment',
        'market analysis and economics',
        'corporate news and mergers',
        'business leadership and management'
    ],
    'science': [
        'scientific research and discoveries',
        'climate change and environment',
        'space exploration and astronomy',
        'medical research and health',
        'physics and chemistry breakthroughs'
    ],
    'sports': [
        'football and soccer news',
        'basketball and baseball games',
        'olympic sports and competitions',
        'sports statistics and analysis',
        'athlete performance and training'
    ],
    'entertainment': [
        'movies and television shows',
        'music and concerts',
        'celebrity news and gossip',
        'gaming and video games',
        'books and literature'
    ],
    'education': [
        'learning and educational content',
        'universities and academic research',
        'online courses and tutorials',
        'teaching methods and pedagogy',
        'student life and campus news'
    ],
    'travel': [
        'travel destinations and guides',
        'vacation planning and tips',
        'airlines and transportation',
        'hotels and accommodation',
        'cultural experiences and food'
    ]
} 