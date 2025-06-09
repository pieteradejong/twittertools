import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useEffect } from 'react';
import { TweetListBase, type TweetData } from './TweetListBase';

interface Topic {
  topic: string;
  count: number;
  avg_score: number;
  max_score: number;
}

interface SemanticTweetListProps {
  isActive: boolean;
}

export function SemanticTweetList({ isActive }: SemanticTweetListProps) {
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [minScore, setMinScore] = useState<number>(0.3);
  const [page, setPage] = useState(0);
  const [filterMode, setFilterMode] = useState<'topic' | 'search'>('topic');
  const limit = 20;
  const queryClient = useQueryClient();

  // Reset page when filters change
  useEffect(() => {
    setPage(0);
  }, [selectedTopic, searchQuery, minScore, filterMode]);

  // Fetch available topics
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: async () => {
      const { data } = await axios.get<{ topics: Topic[] }>('http://localhost:8000/api/likes/topics');
      return data.topics;
    },
    enabled: isActive,
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
  });

  // Fetch filtered tweets
  const fetcher = async () => {
    const offset = page * limit;
    
    if (filterMode === 'search' && searchQuery.trim()) {
      const { data } = await axios.get<TweetData[]>('http://localhost:8000/api/likes/search', {
        params: { query: searchQuery.trim(), limit }
      });
      return data;
    } else if (filterMode === 'topic' && selectedTopic) {
      const { data } = await axios.get<TweetData[]>(`http://localhost:8000/api/likes/by-topic/${selectedTopic}`, {
        params: { limit, offset, min_score: minScore }
      });
      return data;
    } else {
      // Default to regular likes
      const { data } = await axios.get<TweetData[]>(`http://localhost:8000/api/likes?limit=${limit}&offset=${offset}`);
      return data.filter((tweet: TweetData & { status?: string }) => tweet.status === undefined || tweet.status === 'published');
    }
  };

  const { data: tweets, isLoading, error, refetch } = useQuery({
    queryKey: ['semantic-likes', filterMode, selectedTopic, searchQuery, minScore, page],
    queryFn: fetcher,
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // Trigger classification
  const { mutate: runClassification, isPending: isClassifying } = useMutation({
    mutationFn: async () => {
      await axios.post('http://localhost:8000/api/classify/run');
    },
    onSuccess: () => {
      // Refetch topics and tweets after classification
      setTimeout(() => {
        refetch();
        queryClient.invalidateQueries({ queryKey: ['topics'] });
      }, 2000);
    }
  });

  const hasFilters = (filterMode === 'topic' && selectedTopic) || (filterMode === 'search' && searchQuery.trim());

  // Header content with filters
  const headerContent = (
    <div className="space-y-4">
      {/* Title and Actions */}
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold text-gray-900">Semantic Likes Filter</h1>
        <div className="flex gap-2">
          <button 
            className="px-3 py-1 rounded-md bg-green-500 hover:bg-green-600 text-white text-sm font-medium transition-colors disabled:opacity-50"
            onClick={() => runClassification()}
            disabled={isClassifying}
          >
            {isClassifying ? 'Classifying...' : 'Run Classification'}
          </button>
          <button 
            className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors" 
            onClick={() => refetch()}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Filter Mode Toggle */}
      <div className="flex gap-2">
        <button
          className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            filterMode === 'topic' 
              ? 'bg-blue-100 text-blue-700 border border-blue-300' 
              : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
          }`}
          onClick={() => setFilterMode('topic')}
        >
          Filter by Topic
        </button>
        <button
          className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            filterMode === 'search' 
              ? 'bg-blue-100 text-blue-700 border border-blue-300' 
              : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
          }`}
          onClick={() => setFilterMode('search')}
        >
          Semantic Search
        </button>
      </div>

      {/* Topic Filter */}
      {filterMode === 'topic' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                !selectedTopic 
                  ? 'bg-blue-100 text-blue-700 border border-blue-300' 
                  : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
              }`}
              onClick={() => setSelectedTopic('')}
            >
              All Likes
            </button>
            {topicsData?.map((topic) => (
              <button
                key={topic.topic}
                className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                  selectedTopic === topic.topic 
                    ? 'bg-blue-100 text-blue-700 border border-blue-300' 
                    : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                }`}
                onClick={() => setSelectedTopic(topic.topic)}
              >
                {topic.topic} ({topic.count})
              </button>
            ))}
          </div>
          
          {selectedTopic && (
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">
                Min Score: {minScore.toFixed(2)}
              </label>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
                className="flex-1 max-w-xs"
              />
            </div>
          )}
        </div>
      )}

      {/* Search Filter */}
      {filterMode === 'search' && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search likes semantically (e.g., 'AI and technology', 'Miami beaches', 'political news')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
              onClick={() => refetch()}
            >
              Search
            </button>
          </div>
          <p className="text-xs text-gray-500">
            Semantic search finds tweets similar in meaning to your query, not just keyword matches.
          </p>
        </div>
      )}
    </div>
  );

  // Results summary content
  const resultsSummaryContent = (
    <p className="text-sm text-gray-600">
      {hasFilters && (
        <>
          Found {tweets?.length || 0} likes
          {filterMode === 'topic' && selectedTopic && ` in "${selectedTopic}"`}
          {filterMode === 'search' && searchQuery && ` matching "${searchQuery}"`}
          {filterMode === 'topic' && selectedTopic && ` (min score: ${minScore.toFixed(2)})`}
        </>
      )}
      {!hasFilters && `Showing ${tweets?.length || 0} recent likes`}
    </p>
  );

  // Empty state configuration
  const emptyState = {
    icon: "🔍",
    title: hasFilters ? 'No likes found matching your criteria' : 'No likes found',
    description: hasFilters 
      ? 'Try adjusting your filters or running classification first' 
      : 'Try running classification to analyze your likes'
  };

  const loadingMessage = filterMode === 'search' ? 'Searching likes...' : 'Loading filtered likes...';

  return (
    <TweetListBase
      tweets={tweets}
      isLoading={isLoading}
      error={error}
      onRefresh={refetch}
      isActive={isActive}
      headerContent={headerContent}
      loadingMessage={loadingMessage}
      emptyState={emptyState}
      showResultsSummary={true}
      resultsSummaryContent={resultsSummaryContent}
    />
  );
} 