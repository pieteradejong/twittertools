# Comprehensive X API Implementation Guide

This document provides a complete overview of all X (Twitter) API v2 data fetching capabilities implemented in the twittertools project.

## Overview

The comprehensive X API implementation provides:
- **Complete data coverage**: All major X API v2 endpoints
- **Intelligent caching**: 7-day TTL with efficient storage
- **Rate limit management**: Automatic tracking and handling
- **Flexible access**: Both REST API endpoints and CLI tools
- **Rich data storage**: JSON fields for complex data structures

## Implemented Data Types

### 1. Posts/Tweets Data

#### User Tweets
- **Endpoint**: `/2/users/{user_id}/tweets`
- **Rate Limit**: 1,500 requests per 15 minutes
- **Data Fields**: ID, text, created_at, author_id, conversation_id, public_metrics, context_annotations, entities, geo, lang, reply_settings, source
- **API**: `POST /api/comprehensive/fetch/tweets`
- **CLI**: `python scripts/comprehensive_data_fetcher.py user --user-id {id} --data-types tweets`

#### Tweet Search (Recent)
- **Endpoint**: `/2/tweets/search/recent`
- **Rate Limit**: 450 requests per 15 minutes
- **Coverage**: Last 7 days
- **API**: `POST /api/comprehensive/search/tweets/recent`

#### Tweet Search (Full Archive)
- **Endpoint**: `/2/tweets/search/all`
- **Rate Limit**: 300 requests per 15 minutes
- **Coverage**: Complete Twitter history
- **Requirements**: Academic Research access
- **API**: `POST /api/comprehensive/search/tweets/all`

#### Mentions
- **Endpoint**: `/2/users/{user_id}/mentions`
- **Rate Limit**: 450 requests per 15 minutes
- **Data**: Tweets mentioning the specified user

### 2. Engagement Data

#### Likes
- **Endpoint**: `/2/users/{user_id}/liked_tweets`
- **Rate Limit**: 180 requests per 15 minutes
- **Auth**: User context required
- **API**: `POST /api/comprehensive/fetch/likes`
- **CLI**: `python scripts/comprehensive_data_fetcher.py user --user-id {id} --data-types likes`

#### Bookmarks
- **Endpoint**: `/2/users/{user_id}/bookmarks`
- **Rate Limit**: 180 requests per 15 minutes
- **Auth**: User context required
- **API**: `POST /api/comprehensive/fetch/bookmarks`

#### Retweets
- **Endpoint**: `/2/tweets/{tweet_id}/retweeted_by`
- **Rate Limit**: 300 requests per 15 minutes
- **Data**: Users who retweeted a specific tweet

#### Quote Tweets
- **Endpoint**: `/2/tweets/{tweet_id}/quote_tweets`
- **Rate Limit**: 300 requests per 15 minutes
- **Data**: Tweets that quote a specific tweet

### 3. User Data

#### User Profiles
- **Endpoint**: `/2/users`
- **Rate Limit**: 300 requests per 15 minutes
- **Data Fields**: ID, username, name, description, location, URL, profile_image_url, protected, verified, created_at, public_metrics, entities, pinned_tweet_id

#### Followers
- **Endpoint**: `/2/users/{user_id}/followers`
- **Rate Limit**: 180 requests per 15 minutes
- **Max Results**: 1,000 per request
- **API**: `POST /api/comprehensive/fetch/followers`

#### Following
- **Endpoint**: `/2/users/{user_id}/following`
- **Rate Limit**: 180 requests per 15 minutes
- **Max Results**: 1,000 per request
- **API**: `POST /api/comprehensive/fetch/following`

#### Blocks
- **Endpoint**: `/2/users/{user_id}/blocking`
- **Rate Limit**: 180 requests per 15 minutes
- **Auth**: User context required

#### Mutes
- **Endpoint**: `/2/users/{user_id}/muting`
- **Rate Limit**: 180 requests per 15 minutes
- **Auth**: User context required

### 4. Lists Data

#### User Lists
- **Endpoint**: `/2/users/{user_id}/owned_lists`
- **Rate Limit**: 180 requests per 15 minutes
- **Data Fields**: ID, name, description, created_at, follower_count, member_count, private, owner_id
- **API**: `POST /api/comprehensive/fetch/lists`

#### List Members
- **Endpoint**: `/2/lists/{list_id}/members`
- **Rate Limit**: 180 requests per 15 minutes
- **Max Results**: 100 per request

#### List Followers
- **Endpoint**: `/2/lists/{list_id}/followers`
- **Rate Limit**: 180 requests per 15 minutes

#### List Tweets
- **Endpoint**: `/2/lists/{list_id}/tweets`
- **Rate Limit**: 180 requests per 15 minutes
- **Data**: Recent tweets from list members

### 5. Spaces Data

#### Spaces Search
- **Endpoint**: `/2/spaces/search`
- **Rate Limit**: 300 requests per 15 minutes
- **Data Fields**: ID, state, title, created_at, started_at, ended_at, host_ids, speaker_ids, participant_count, subscriber_count, is_ticketed, lang
- **API**: `POST /api/comprehensive/fetch/spaces`

#### Space Tweets
- **Endpoint**: `/2/spaces/{space_id}/tweets`
- **Rate Limit**: 300 requests per 15 minutes
- **Data**: Tweets shared in a Space

#### Space Buyers
- **Endpoint**: `/2/spaces/{space_id}/buyers`
- **Rate Limit**: 300 requests per 15 minutes
- **Data**: Users who purchased tickets to a Space

### 6. Direct Messages

#### DM Events
- **Endpoint**: `/2/dm_conversations/with/{participant_id}/dm_events`
- **Rate Limit**: 300 requests per 15 minutes
- **Auth**: User context required
- **Data Fields**: ID, event_type, text, created_at, sender_id, dm_conversation_id, participant_ids, referenced_tweets, attachments
- **API**: `POST /api/comprehensive/fetch/direct-messages`

#### DM Conversations
- **Endpoint**: `/2/dm_conversations`
- **Rate Limit**: 300 requests per 15 minutes
- **Data**: List of DM conversations

### 7. Communities

#### Community Search
- **Endpoint**: `/2/communities/search`
- **Rate Limit**: 300 requests per 15 minutes
- **Data Fields**: ID, name, description, created_at, access, join_policy, member_count
- **API**: `POST /api/comprehensive/search/communities`

#### Community Tweets
- **Endpoint**: `/2/communities/{community_id}/tweets`
- **Rate Limit**: 300 requests per 15 minutes

#### Community Members
- **Endpoint**: `/2/communities/{community_id}/members`
- **Rate Limit**: 300 requests per 15 minutes

### 8. Media Data

#### Media Lookup
- **Endpoint**: `/2/media/{media_id}`
- **Rate Limit**: 300 requests per 15 minutes
- **Data Fields**: media_key, type, URL, duration_ms, height, width, preview_image_url, alt_text, public_metrics, variants

### 9. Trends

#### Trending Topics
- **Endpoint**: `/2/trends/by/woeid/{woeid}`
- **Rate Limit**: 75 requests per 15 minutes
- **Data Fields**: trend_name, tweet_volume
- **API**: `POST /api/comprehensive/fetch/trends`
- **Common WOEIDs**: 1 (Worldwide), 23424977 (United States), 44418 (United Kingdom)

### 10. Compliance

#### Compliance Jobs
- **Endpoint**: `/2/compliance/jobs`
- **Rate Limit**: 150 requests per 15 minutes
- **Data**: Batch compliance job status and results

## Database Schema

### Core Tables

#### tweets_comprehensive
```sql
CREATE TABLE tweets_comprehensive (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TEXT,
    author_id TEXT,
    conversation_id TEXT,
    in_reply_to_user_id TEXT,
    referenced_tweets TEXT,      -- JSON array
    public_metrics TEXT,         -- JSON object
    context_annotations TEXT,    -- JSON array
    entities TEXT,              -- JSON object
    geo TEXT,                   -- JSON object
    lang TEXT,
    possibly_sensitive BOOLEAN,
    reply_settings TEXT,
    source TEXT,
    cached_at TEXT,
    expires_at TEXT,
    data_source TEXT DEFAULT 'api'
);
```

#### users_comprehensive
```sql
CREATE TABLE users_comprehensive (
    id TEXT PRIMARY KEY,
    username TEXT,
    name TEXT,
    description TEXT,
    location TEXT,
    url TEXT,
    profile_image_url TEXT,
    protected BOOLEAN,
    verified BOOLEAN,
    created_at TEXT,
    public_metrics TEXT,        -- JSON object
    entities TEXT,              -- JSON object
    pinned_tweet_id TEXT,
    cached_at TEXT,
    expires_at TEXT,
    data_source TEXT DEFAULT 'api'
);
```

#### Additional Tables
- `spaces` - Spaces data
- `lists_comprehensive` - Enhanced lists data
- `direct_messages` - DM conversations and events
- `communities` - Community information
- `media_comprehensive` - Media metadata
- `trends` - Trending topics
- `relationships` - Follow/block/mute relationships
- `engagement` - Like/retweet/quote/bookmark data
- `api_usage` - API usage tracking and rate limit monitoring

## API Endpoints

### Statistics and Monitoring

#### Get Comprehensive Stats
```http
GET /api/comprehensive/stats
```
Returns cached data counts and API usage statistics.

#### Get Cached Tweet Data
```http
GET /api/comprehensive/data/tweets?limit=20&offset=0&author_id={id}
```

#### Get Cached User Data
```http
GET /api/comprehensive/data/users?limit=20&offset=0&username={username}
```

### Data Fetching Endpoints

All fetching endpoints follow the pattern:
```http
POST /api/comprehensive/fetch/{data_type}
```

Examples:
- `POST /api/comprehensive/fetch/tweets?user_id={id}&max_results=100`
- `POST /api/comprehensive/fetch/likes?user_id={id}&max_results=100`
- `POST /api/comprehensive/fetch/followers?user_id={id}&max_results=1000`

### Search Endpoints

```http
POST /api/comprehensive/search/tweets/recent?query={query}&max_results=100
POST /api/comprehensive/search/tweets/all?query={query}&max_results=500
POST /api/comprehensive/search/communities?query={query}&max_results=100
```

## CLI Usage

### Basic Commands

```bash
# Get statistics
python scripts/comprehensive_data_fetcher.py stats

# Fetch user tweets
python scripts/comprehensive_data_fetcher.py user --user-id 123456789 --data-types tweets

# Fetch multiple data types
python scripts/comprehensive_data_fetcher.py user --user-id 123456789 --data-types tweets likes --max-results 50
```

### Advanced Usage

```bash
# Search recent tweets
python scripts/comprehensive_data_fetcher.py search --query "python programming" --search-type recent --max-results 100

# Search full archive (requires Academic Research access)
python scripts/comprehensive_data_fetcher.py search --query "climate change" --search-type all --max-results 500

# Fetch Spaces
python scripts/comprehensive_data_fetcher.py spaces --query "tech talk" --max-results 50

# Fetch direct messages
python scripts/comprehensive_data_fetcher.py dm --participant-id 987654321 --max-results 100

# Search communities
python scripts/comprehensive_data_fetcher.py communities --query "developers" --max-results 50

# Fetch trending topics
python scripts/comprehensive_data_fetcher.py trends --woeid 1  # Worldwide trends
```

## Rate Limiting and Best Practices

### Rate Limit Management
- Automatic rate limit detection and handling
- Intelligent request spacing
- Rate limit status tracking in `api_usage` table
- Graceful degradation when limits are reached

### Caching Strategy
- **Default TTL**: 7 days for most data
- **Trends TTL**: 1 hour (more volatile)
- **Automatic cleanup**: Expired entries removed on access
- **Cache-first approach**: Check cache before API calls

### Best Practices

1. **Start Small**: Begin with small `max_results` values
2. **Monitor Usage**: Check `/api/comprehensive/stats` regularly
3. **Respect Limits**: Use appropriate delays between requests
4. **Cache Awareness**: Leverage cached data when possible
5. **Error Handling**: Implement retry logic with exponential backoff

## Authentication Requirements

### User Context (OAuth 1.0a)
Required for:
- Likes
- Bookmarks
- Direct Messages
- Blocks/Mutes
- Private account data

### App Context (Bearer Token)
Sufficient for:
- Public tweets
- User profiles
- Lists
- Spaces
- Trends
- Communities

### Academic Research Access
Required for:
- Full archive search (`/2/tweets/search/all`)
- Extended historical data
- Higher rate limits on some endpoints

## Error Handling

### Common Error Responses
- `429 Too Many Requests`: Rate limit exceeded
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource doesn't exist
- `500 Internal Server Error`: API or service error

### Retry Strategy
1. **Rate Limits**: Wait for reset time
2. **Temporary Errors**: Exponential backoff
3. **Authentication**: Re-authenticate if needed
4. **Permanent Errors**: Log and skip

## Monitoring and Analytics

### API Usage Tracking
```sql
SELECT endpoint, COUNT(*) as requests, AVG(response_time_ms) as avg_response_time
FROM api_usage 
WHERE timestamp > datetime('now', '-24 hours')
GROUP BY endpoint
ORDER BY requests DESC;
```

### Data Freshness
```sql
SELECT 
    'tweets_comprehensive' as table_name,
    COUNT(*) as total_records,
    COUNT(CASE WHEN expires_at > datetime('now') THEN 1 END) as fresh_records,
    MAX(cached_at) as last_update
FROM tweets_comprehensive;
```

### Rate Limit Status
```sql
SELECT endpoint, status_code, COUNT(*) as count
FROM api_usage 
WHERE timestamp > datetime('now', '-1 hour')
GROUP BY endpoint, status_code
ORDER BY endpoint, status_code;
```

## Future Enhancements

### Planned Features
1. **Real-time Streaming**: Filtered and volume streams
2. **Batch Processing**: Bulk data operations
3. **Advanced Analytics**: Sentiment analysis, trend detection
4. **Export Formats**: CSV, Parquet, JSON Lines
5. **Webhook Integration**: Real-time data notifications
6. **Dashboard UI**: Web interface for data exploration

### Scalability Considerations
1. **Database Partitioning**: Time-based partitions for large datasets
2. **Async Processing**: Background job queues
3. **Distributed Caching**: Redis/Memcached integration
4. **Load Balancing**: Multiple API instances
5. **Data Archival**: Cold storage for historical data

## Conclusion

This comprehensive X API implementation provides complete coverage of Twitter's data ecosystem with intelligent caching, rate limit management, and flexible access patterns. The system is designed for both interactive exploration and automated data collection workflows.

For questions or contributions, please refer to the project documentation or open an issue on the repository. 