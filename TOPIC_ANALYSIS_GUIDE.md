# Topic Analysis System Guide

## Overview

The Topic Analysis System provides comprehensive, modular functionality for analyzing and filtering Twitter content by semantic topics. It can classify tweets, likes, replies, and other Twitter data into topics like "technology", "politics", "miami", etc., and allows for advanced filtering and search capabilities.

## Key Features

### 🎯 **Modular Design**
- Works with any Twitter data type (tweets, likes, replies, bookmarks)
- Reusable components across different parts of the application
- Configurable topic definitions and thresholds

### 🧠 **Advanced AI Classification**
- Uses Sentence Transformers (all-MiniLM-L6-v2) for semantic understanding
- Zero-shot classification (no training data required)
- Multi-label support (content can belong to multiple topics)
- Configurable similarity thresholds

### 🔍 **Powerful Filtering & Search**
- Filter by specific topics with score thresholds
- Exclude unwanted topics
- Semantic search with natural language queries
- Sort by relevance, score, or date

### 🎨 **Rich Frontend Integration**
- Reusable `TopicFilter` component
- Generic `TopicAnalysisView` for any data type
- Real-time filtering and analysis
- Beautiful, responsive UI with Tailwind CSS

## Architecture

### Backend Components

#### 1. `TopicAnalyzer` (Core Service)
```python
from src.topic_analyzer import TopicAnalyzer, DataSource, TopicFilter

# Initialize analyzer
analyzer = TopicAnalyzer(similarity_threshold=0.3)

# Analyze different data sources
results = analyzer.analyze_data_source(DataSource.LIKES, limit=100)

# Filter by topics
topic_filter = TopicFilter(
    topics=["technology", "politics"],
    min_score=0.4,
    max_results=50,
    sort_by="score"
)
filtered_data = analyzer.filter_by_topics(DataSource.TWEETS, topic_filter)
```

#### 2. Data Sources
- `TWEETS` - User's tweets
- `LIKES` - Liked tweets
- `REPLIES` - Reply tweets
- `BOOKMARKS` - Bookmarked tweets
- `CUSTOM` - Custom SQL queries

#### 3. API Endpoints
```
GET  /api/topics/overview              # Topic distribution overview
GET  /api/topics/analyze/{data_source} # Analyze specific data source
POST /api/topics/filter               # Filter by topic criteria
GET  /api/topics/search               # Semantic search
POST /api/topics/add-custom           # Add custom topics
GET  /api/topics/export/{data_source} # Export analysis results
```

### Frontend Components

#### 1. `TopicFilter` Component
Reusable filtering component that can be used with any data source:

```tsx
import { TopicFilter } from '../common/TopicFilter';

<TopicFilter
  dataSource="likes"
  onFilterChange={setFilteredData}
  onLoadingChange={setIsLoading}
  onErrorChange={setError}
  showAnalyzeButton={true}
  showCustomTopics={true}
/>
```

#### 2. `TopicAnalysisView` Component
Complete analysis view for any Twitter data type:

```tsx
import { TopicAnalysisView } from '../tweets/TopicAnalysisView';

<TopicAnalysisView
  dataSource="tweets"
  isActive={true}
  title="Tweet Topic Analysis"
  showCustomTopics={true}
/>
```

## Usage Examples

### 1. Basic Topic Analysis

```python
# Quick analysis of likes by technology topic
from src.topic_analyzer import analyze_likes_by_topic

tech_likes = analyze_likes_by_topic("technology", min_score=0.3, limit=20)
print(f"Found {len(tech_likes)} technology-related likes")
```

### 2. Advanced Filtering

```python
from src.topic_analyzer import TopicAnalyzer, DataSource, TopicFilter

analyzer = TopicAnalyzer()

# Create complex filter
filter_config = TopicFilter(
    topics=["technology", "politics"],     # Include these topics
    exclude_topics=["miami"],              # Exclude this topic
    min_score=0.4,                        # High confidence only
    max_results=100,                      # Limit results
    sort_by="score"                       # Sort by relevance
)

# Apply filter
results = analyzer.filter_by_topics(DataSource.TWEETS, filter_config)
```

### 3. Semantic Search

```python
# Search across all classified content
search_results = analyzer.semantic_search(
    "artificial intelligence and machine learning",
    limit=20
)

# Search within specific data source
likes_results = analyzer.semantic_search(
    "Miami beaches and nightlife",
    data_source=DataSource.LIKES,
    limit=10
)
```

### 4. Custom Topics

```python
# Add a custom topic
analyzer.add_custom_topic("crypto", [
    "cryptocurrency and blockchain technology",
    "bitcoin ethereum and digital assets",
    "decentralized finance and NFTs",
    "crypto trading and investment"
])

# Use the new topic
crypto_filter = TopicFilter(topics=["crypto"], min_score=0.3)
crypto_content = analyzer.filter_by_topics(DataSource.LIKES, crypto_filter)
```

### 5. Export Analysis

```python
# Export results to JSON
json_path = analyzer.export_topic_analysis(DataSource.TWEETS, "json")

# Export to CSV
csv_path = analyzer.export_topic_analysis(DataSource.LIKES, "csv")
```

## Default Topics

The system comes with three pre-configured topics:

### 🔧 Technology
- Artificial intelligence and machine learning
- Software development and programming
- Tech startups and innovation
- Coding and software engineering
- AI tools and automation

### 🏛️ Politics
- Government policy and legislation
- Political campaigns and elections
- Democratic processes and voting
- Political parties and candidates
- Policy debates and governance

### 🌴 Miami
- Miami Florida city life
- South Beach and Miami Beach
- Miami nightlife and entertainment
- Miami real estate and housing
- Miami weather and beaches

## Frontend Usage

### Navigation
The topic analysis features are available through these navigation tabs:
- **Topic Analysis - Tweets**: Analyze your tweets by topic
- **Topic Analysis - Likes**: Analyze your likes by topic  
- **Topic Analysis - Replies**: Analyze your replies by topic

### Features Available in UI

#### 1. **Filter by Topic Mode**
- Select multiple topics to include
- Exclude unwanted topics
- Adjust minimum similarity score (0.1 - 1.0)
- Sort by score, date, or relevance

#### 2. **Semantic Search Mode**
- Natural language search queries
- Find content similar in meaning (not just keywords)
- Example queries:
  - "AI and technology"
  - "Miami beaches"
  - "political news"

#### 3. **Overview Mode**
- View topic distribution statistics
- See total items and topics
- Understand classification threshold
- Topic percentages and counts

#### 4. **Custom Topics** (when enabled)
- Add new topic definitions
- Define multiple seed phrases per topic
- Immediately available for filtering

## API Reference

### Get Topic Overview
```http
GET /api/topics/overview
```
Returns topic distribution with counts and percentages.

### Analyze Data Source
```http
GET /api/topics/analyze/{data_source}?limit=100&custom_query=SELECT...
```
Analyze specific data source for topics.

### Filter by Topics
```http
POST /api/topics/filter
Content-Type: application/json

{
  "data_source": "likes",
  "topics": ["technology", "politics"],
  "exclude_topics": ["miami"],
  "min_score": 0.3,
  "max_results": 100,
  "sort_by": "score"
}
```

### Semantic Search
```http
GET /api/topics/search?query=AI%20technology&data_source=tweets&limit=20
```

### Add Custom Topic
```http
POST /api/topics/add-custom
Content-Type: application/json

{
  "topic_name": "crypto",
  "seed_phrases": [
    "cryptocurrency and blockchain",
    "bitcoin ethereum digital assets"
  ]
}
```

### Export Analysis
```http
GET /api/topics/export/{data_source}?format=json
```

## Performance Considerations

### Model Loading
- First use: ~2-3 seconds to load the sentence transformer model
- Subsequent uses: Cached in memory for fast access

### Classification Speed
- ~0.6 seconds per tweet on average
- Batch processing for efficiency
- Background processing available via API

### Database Storage
- Classifications stored in `theme_classifications.db`
- Indexed for fast retrieval by topic and score
- Supports incremental updates

## Best Practices

### 1. **Topic Definition**
- Use 3-5 seed phrases per topic
- Make phrases specific and descriptive
- Include different aspects of the topic
- Test with sample content

### 2. **Similarity Thresholds**
- Start with 0.3 for balanced results
- Lower (0.2) for broader matching
- Higher (0.5+) for precise matching
- Adjust based on your content

### 3. **Performance Optimization**
- Run classification in background for large datasets
- Use appropriate batch sizes (32 recommended)
- Cache results for repeated queries
- Monitor database size and cleanup old classifications

### 4. **Custom Topics**
- Be specific with seed phrases
- Test new topics with known content
- Iterate on phrases based on results
- Consider topic overlap and conflicts

## Troubleshooting

### Common Issues

#### 1. **No Results Found**
- Check if data has been classified
- Run analysis first via "Analyze" button
- Lower similarity threshold
- Verify topic names are correct

#### 2. **Slow Performance**
- Model loading on first use is normal
- Large datasets may take time to classify
- Use background processing for bulk operations
- Consider limiting batch sizes

#### 3. **Unexpected Classifications**
- Review seed phrases for topics
- Check similarity threshold settings
- Consider adding negative examples
- Refine topic definitions

#### 4. **API Errors**
- Verify data source names are valid
- Check request format and parameters
- Ensure database is accessible
- Review server logs for details

## Future Enhancements

### Planned Features
- **Multi-language Support**: Classify content in different languages
- **Temporal Analysis**: Track topic trends over time
- **Topic Clustering**: Automatically discover new topics
- **Sentiment Integration**: Combine topic analysis with sentiment
- **Advanced Visualizations**: Charts and graphs for topic distribution
- **Batch Operations**: UI for bulk classification and export

### Integration Opportunities
- **List Management**: Auto-categorize Twitter lists by topic
- **Content Curation**: Suggest content based on topic preferences
- **Analytics Dashboard**: Comprehensive topic analytics
- **Recommendation Engine**: Topic-based content recommendations

## Support

For questions, issues, or feature requests related to the topic analysis system:

1. Check this documentation first
2. Review the test script: `test_topic_analysis.py`
3. Examine the API documentation at `/docs`
4. Look at the source code in `src/topic_analyzer.py`

The system is designed to be extensible and customizable for your specific use cases. Happy analyzing! 🎯 