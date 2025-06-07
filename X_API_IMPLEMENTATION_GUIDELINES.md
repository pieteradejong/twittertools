# X API Implementation Guidelines

## Overview
These guidelines provide a comprehensive framework for implementing X (Twitter) API v2 data fetching capabilities. Follow these patterns to create a robust, scalable, and maintainable X API integration.

## Core Architecture Principles

### 1. Service-Oriented Design
- **Single Responsibility**: Create dedicated services for each major functionality
- **Dependency Injection**: Use constructor injection for dependencies like database connections and API clients
- **Interface Segregation**: Define clear interfaces for different data types and operations
- **Modular Structure**: Separate concerns into distinct modules (auth, caching, API calls, storage)

### 2. Data Type Organization
```python
class DataType(Enum):
    # Posts/Tweets
    TWEETS = "tweets"
    SEARCH_RECENT = "search_recent"
    SEARCH_ALL = "search_all"
    MENTIONS = "mentions"
    
    # Engagement
    LIKES = "likes"
    BOOKMARKS = "bookmarks"
    RETWEETS = "retweets"
    QUOTES = "quotes"
    
    # Users & Relationships
    USERS = "users"
    FOLLOWERS = "followers"
    FOLLOWING = "following"
    BLOCKS = "blocks"
    MUTES = "mutes"
    
    # Lists
    LISTS = "lists"
    LIST_MEMBERS = "list_members"
    LIST_TWEETS = "list_tweets"
    
    # Advanced Features
    SPACES = "spaces"
    DIRECT_MESSAGES = "direct_messages"
    COMMUNITIES = "communities"
    TRENDS = "trends"
    MEDIA = "media"
```

### 3. Configuration-Driven Endpoints
```python
@dataclass
class APIEndpoint:
    endpoint: str
    method: str
    auth_required: str  # 'user', 'app', 'both'
    rate_limit: int
    window_minutes: int
    fields: List[str]
    expansions: List[str]
    max_results: int = 100
```

## Database Design Patterns

### 1. Comprehensive Schema Design
- **JSON Fields**: Use JSON columns for complex nested data (metrics, entities, annotations)
- **Proper Indexing**: Create indexes on frequently queried fields (author_id, created_at, username)
- **TTL Support**: Include `cached_at` and `expires_at` fields for all tables
- **Data Source Tracking**: Track whether data came from API, archive, or other sources
- **Relationship Tables**: Use junction tables for many-to-many relationships

### 2. Core Table Structure Pattern
```sql
CREATE TABLE {data_type}_comprehensive (
    id TEXT PRIMARY KEY,
    -- Core fields specific to data type
    {specific_fields},
    -- JSON fields for complex data
    public_metrics TEXT,     -- JSON object
    entities TEXT,           -- JSON object
    context_annotations TEXT, -- JSON array
    -- Caching and metadata
    cached_at TEXT,
    expires_at TEXT,
    data_source TEXT DEFAULT 'api'
);
```

### 3. Essential Tables to Implement
- `tweets_comprehensive`: Enhanced tweet data with full metadata
- `users_comprehensive`: Complete user profiles with metrics
- `relationships`: Follow/block/mute relationships
- `engagement`: Likes, retweets, quotes, bookmarks
- `lists_comprehensive`: List data with member/follower counts
- `spaces`: Spaces data with participant information
- `direct_messages`: DM conversations and events
- `communities`: Community information and membership
- `media_comprehensive`: Media metadata and metrics
- `trends`: Trending topics with volume data
- `api_usage`: API call tracking and rate limit monitoring

## Caching Strategy

### 1. Intelligent TTL Management
- **Standard Data**: 7-day TTL for most content (tweets, users, lists)
- **Volatile Data**: 1-hour TTL for rapidly changing data (trends)
- **Relationship Data**: 24-hour TTL for follows/blocks/mutes
- **Media Data**: 30-day TTL for media metadata
- **Profile Data**: 3-day TTL for user profiles

### 2. Cache-First Approach
```python
def get_data(self, data_type: DataType, **kwargs):
    # 1. Check cache first
    cached_data = self._get_cached_data(data_type, **kwargs)
    if cached_data and not self._is_expired(cached_data):
        return cached_data
    
    # 2. Fetch from API if cache miss/expired
    fresh_data = self._fetch_from_api(data_type, **kwargs)
    
    # 3. Store in cache
    self._store_in_cache(data_type, fresh_data)
    
    return fresh_data
```

### 3. Automatic Cleanup
- Implement background cleanup of expired cache entries
- Use database triggers or scheduled jobs for maintenance
- Monitor cache hit rates and storage usage

## Rate Limit Management

### 1. Rate Limit Tracking
```python
def _log_api_usage(self, endpoint: str, method: str, response_time: int, 
                   status_code: int, rate_limit_remaining: int = None):
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT INTO api_usage 
            (endpoint, method, timestamp, response_time_ms, status_code, 
             rate_limit_remaining, rate_limit_reset)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (endpoint, method, datetime.now().isoformat(), 
              response_time, status_code, rate_limit_remaining, 
              self._calculate_reset_time()))
```

### 2. Intelligent Request Spacing
- Monitor remaining rate limit from API responses
- Implement exponential backoff for rate limit errors
- Queue requests when approaching limits
- Prioritize high-value requests when rate limited

### 3. Multi-Endpoint Coordination
- Track rate limits separately for each endpoint
- Balance requests across different endpoint categories
- Use app-only auth for public data to preserve user auth limits

## Authentication Strategy

### 1. Multi-Auth Support
```python
class AuthManager:
    def __init__(self):
        self.user_auth = self._setup_user_auth()  # OAuth 1.0a
        self.app_auth = self._setup_app_auth()    # Bearer Token
        
    def get_client(self, auth_type: str):
        if auth_type == 'user':
            return self.user_auth
        elif auth_type == 'app':
            return self.app_auth
        else:
            # Choose best available auth
            return self.user_auth if self.user_auth else self.app_auth
```

### 2. Auth Requirements by Data Type
- **User Context Required**: Likes, bookmarks, DMs, blocks, mutes
- **App Context Sufficient**: Public tweets, user profiles, lists, trends
- **Academic Access Required**: Full archive search, compliance jobs

### 3. Secure Credential Management
- Never store API secrets in plaintext
- Use environment variables or secure key management
- Hash credentials for caching authentication status
- Implement credential rotation support

## API Implementation Patterns

### 1. Unified Data Fetching Interface
```python
def fetch_data(self, data_type: DataType, **kwargs) -> Dict[str, Any]:
    # 1. Validate parameters
    self._validate_parameters(data_type, kwargs)
    
    # 2. Get endpoint configuration
    endpoint_config = self.endpoints[data_type]
    
    # 3. Check rate limits
    if not self._can_make_request(endpoint_config):
        return self._handle_rate_limit(data_type)
    
    # 4. Make API request
    response = self._make_api_request(endpoint_config, kwargs)
    
    # 5. Store data
    if response.get('data'):
        self._store_data(data_type, response)
    
    # 6. Log usage
    self._log_api_usage(endpoint_config.endpoint, 'GET', 
                       response.get('response_time', 0), 
                       response.get('status_code', 200))
    
    return response
```

### 2. Flexible Parameter Handling
```python
def _build_request_params(self, endpoint_config: APIEndpoint, kwargs: Dict) -> Dict:
    params = {
        'max_results': min(kwargs.get('max_results', endpoint_config.max_results), 
                          endpoint_config.max_results)
    }
    
    # Add field parameters
    if endpoint_config.fields:
        field_param = self._get_field_param_name(endpoint_config)
        params[field_param] = ','.join(endpoint_config.fields)
    
    # Add expansions
    if endpoint_config.expansions:
        params['expansions'] = ','.join(endpoint_config.expansions)
    
    # Add endpoint-specific parameters
    params.update(self._get_specific_params(endpoint_config, kwargs))
    
    return params
```

### 3. Robust Error Handling
```python
def _make_api_request(self, endpoint_config: APIEndpoint, kwargs: Dict):
    try:
        response = self.client.request(endpoint_config.endpoint, 
                                     self._build_request_params(endpoint_config, kwargs))
        return self._process_response(response)
    except tweepy.TooManyRequests:
        logger.warning(f"Rate limited for {endpoint_config.endpoint}")
        return {'data': [], 'meta': {}, 'error': 'Rate limited'}
    except tweepy.Unauthorized:
        logger.error(f"Unauthorized access to {endpoint_config.endpoint}")
        return {'data': [], 'meta': {}, 'error': 'Unauthorized'}
    except Exception as e:
        logger.error(f"API error for {endpoint_config.endpoint}: {str(e)}")
        return {'data': [], 'meta': {}, 'error': str(e)}
```

## Data Storage Patterns

### 1. Type-Specific Storage Methods
```python
def _store_data(self, data_type: DataType, response: Dict[str, Any]):
    data = response.get('data', [])
    includes = response.get('includes', {})
    
    storage_methods = {
        DataType.TWEETS: self._store_tweets,
        DataType.USERS: self._store_users,
        DataType.LIKES: lambda conn, data, inc: self._store_engagement(conn, data, 'like'),
        DataType.LISTS: self._store_lists,
        DataType.SPACES: self._store_spaces,
        # ... other mappings
    }
    
    with sqlite3.connect(self.db_path) as conn:
        storage_method = storage_methods.get(data_type)
        if storage_method:
            storage_method(conn, data, includes)
```

### 2. JSON Field Handling
```python
def _store_tweets(self, conn: sqlite3.Connection, tweets: List[Dict], includes: Dict):
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(days=self.cache_ttl_days)).isoformat()
    
    for tweet in tweets:
        conn.execute("""
            INSERT OR REPLACE INTO tweets_comprehensive 
            (id, text, created_at, author_id, public_metrics, entities, 
             context_annotations, cached_at, expires_at, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tweet.get('id'),
            tweet.get('text'),
            tweet.get('created_at'),
            tweet.get('author_id'),
            json.dumps(tweet.get('public_metrics', {})),
            json.dumps(tweet.get('entities', {})),
            json.dumps(tweet.get('context_annotations', [])),
            now,
            expires,
            'api'
        ))
```

### 3. Relationship Data Handling
```python
def _store_relationships(self, conn: sqlite3.Connection, users: List[Dict], 
                        relationship_type: str, source_user_id: str):
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(days=1)).isoformat()
    
    for user in users:
        relationship_id = f"{source_user_id}_{user.get('id')}_{relationship_type}"
        conn.execute("""
            INSERT OR REPLACE INTO relationships 
            (id, source_user_id, target_user_id, relationship_type, 
             created_at, cached_at, expires_at, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (relationship_id, source_user_id, user.get('id'), 
              relationship_type, now, now, expires, 'api'))
```

## API Endpoint Design

### 1. RESTful Endpoint Structure
```python
# Data fetching endpoints
@app.post("/api/comprehensive/fetch/{data_type}")
async def fetch_data(data_type: str, params: Dict[str, Any]):
    pass

# Search endpoints
@app.post("/api/comprehensive/search/{search_type}")
async def search_data(search_type: str, query: SearchQuery):
    pass

# Cached data access
@app.get("/api/comprehensive/data/{data_type}")
async def get_cached_data(data_type: str, limit: int = 100, offset: int = 0):
    pass

# Statistics and monitoring
@app.get("/api/comprehensive/stats")
async def get_stats():
    pass
```

### 2. Request/Response Models
```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class FetchRequest(BaseModel):
    user_id: Optional[str] = None
    query: Optional[str] = None
    max_results: Optional[int] = 100
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class APIResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    meta: Dict[str, Any]
    error: Optional[str] = None
    cached: bool = False
```

### 3. Parameter Validation
```python
def validate_fetch_params(data_type: DataType, params: Dict[str, Any]) -> Dict[str, Any]:
    required_params = {
        DataType.TWEETS: ['user_id'],
        DataType.SEARCH_RECENT: ['query'],
        DataType.FOLLOWERS: ['user_id'],
        DataType.TRENDS: ['woeid'],
        # ... other requirements
    }
    
    if data_type in required_params:
        for param in required_params[data_type]:
            if param not in params or not params[param]:
                raise ValueError(f"Missing required parameter: {param}")
    
    return params
```

## CLI Interface Design

### 1. Subcommand Structure
```python
import argparse

def create_parser():
    parser = argparse.ArgumentParser(description='Comprehensive X API Data Fetcher')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # User data commands
    user_parser = subparsers.add_parser('user', help='Fetch user-related data')
    user_parser.add_argument('--user-id', required=True, help='User ID to fetch data for')
    user_parser.add_argument('--data-types', nargs='+', 
                           choices=['tweets', 'likes', 'followers', 'following'],
                           help='Types of data to fetch')
    
    # Search commands
    search_parser = subparsers.add_parser('search', help='Search for content')
    search_parser.add_argument('--query', required=True, help='Search query')
    search_parser.add_argument('--type', choices=['recent', 'all'], default='recent')
    
    # Other subcommands...
    
    return parser
```

### 2. Command Execution Pattern
```python
def execute_command(args):
    service = ComprehensiveXAPIService()
    
    if args.command == 'user':
        results = {}
        for data_type in args.data_types:
            results[data_type] = service.fetch_data(
                DataType(data_type), 
                user_id=args.user_id
            )
        return results
    
    elif args.command == 'search':
        search_type = DataType.SEARCH_ALL if args.type == 'all' else DataType.SEARCH_RECENT
        return service.fetch_data(search_type, query=args.query)
```

## Monitoring and Analytics

### 1. Usage Statistics
```python
def get_comprehensive_stats(self) -> Dict[str, Any]:
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # API usage stats
        api_stats = self._get_api_usage_stats(conn)
        
        # Cache statistics
        cache_stats = self._get_cache_stats(conn)
        
        # Data freshness
        freshness_stats = self._get_data_freshness_stats(conn)
        
        return {
            'api_usage': api_stats,
            'cache_performance': cache_stats,
            'data_freshness': freshness_stats,
            'timestamp': datetime.now().isoformat()
        }
```

### 2. Performance Monitoring
```python
def _monitor_performance(self, operation: str, duration: float, success: bool):
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT INTO performance_metrics 
            (operation, duration_ms, success, timestamp)
            VALUES (?, ?, ?, ?)
        """, (operation, int(duration * 1000), success, datetime.now().isoformat()))
```

## Security Best Practices

### 1. Credential Security
- Store API keys in environment variables or secure vaults
- Use hashed tokens for authentication caching
- Implement credential rotation mechanisms
- Never log sensitive authentication data

### 2. Data Privacy
- Respect user privacy settings and protected accounts
- Implement data retention policies
- Provide data deletion capabilities
- Follow GDPR and other privacy regulations

### 3. Rate Limit Compliance
- Never attempt to circumvent rate limits
- Implement proper backoff strategies
- Monitor and alert on unusual usage patterns
- Respect API terms of service

## Testing Strategy

### 1. Unit Testing
```python
def test_data_fetching():
    service = ComprehensiveXAPIService()
    
    # Mock API responses
    with patch.object(service, '_make_api_request') as mock_request:
        mock_request.return_value = {'data': [{'id': '123', 'text': 'test'}]}
        
        result = service.fetch_data(DataType.TWEETS, user_id='test_user')
        
        assert result['data'][0]['id'] == '123'
        assert mock_request.called
```

### 2. Integration Testing
- Test with real API endpoints using test accounts
- Validate data storage and retrieval
- Test rate limit handling
- Verify caching behavior

### 3. Performance Testing
- Load test with high request volumes
- Monitor memory usage with large datasets
- Test database performance with millions of records
- Validate cache hit rates under load

## Deployment Considerations

### 1. Environment Configuration
```python
# config.py
import os

class Config:
    TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
    TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
    TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
    
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/x_data.db')
    CACHE_TTL_DAYS = int(os.getenv('CACHE_TTL_DAYS', '7'))
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

### 2. Production Readiness
- Implement proper logging with structured formats
- Add health check endpoints
- Monitor disk space for database growth
- Implement backup and recovery procedures
- Use connection pooling for database access

### 3. Scalability Considerations
- Consider database sharding for very large datasets
- Implement read replicas for high-query loads
- Use message queues for background processing
- Consider caching layers (Redis) for frequently accessed data

## Implementation Checklist

### Core Components
- [ ] Service class with comprehensive data type support
- [ ] Database schema with all required tables
- [ ] Authentication manager with multi-auth support
- [ ] Rate limit tracking and management
- [ ] Intelligent caching with TTL support
- [ ] Error handling and retry logic

### API Endpoints
- [ ] Data fetching endpoints for all data types
- [ ] Search endpoints for tweets, users, spaces, communities
- [ ] Cached data access endpoints
- [ ] Statistics and monitoring endpoints
- [ ] Health check and status endpoints

### CLI Interface
- [ ] Subcommand structure for different operations
- [ ] Parameter validation and help text
- [ ] Output formatting (JSON, table, etc.)
- [ ] Progress indicators for long operations

### Monitoring & Analytics
- [ ] API usage tracking
- [ ] Performance metrics collection
- [ ] Cache hit rate monitoring
- [ ] Data freshness tracking
- [ ] Error rate monitoring

### Security & Compliance
- [ ] Secure credential management
- [ ] Rate limit compliance
- [ ] Data privacy protection
- [ ] Audit logging
- [ ] Access control mechanisms

### Testing & Quality
- [ ] Unit tests for core functionality
- [ ] Integration tests with real API
- [ ] Performance tests under load
- [ ] Security testing
- [ ] Documentation and examples

This comprehensive guide provides the foundation for implementing a robust, scalable, and maintainable X API integration. Follow these patterns and principles to create a production-ready system that can handle the full scope of X API v2 capabilities.
