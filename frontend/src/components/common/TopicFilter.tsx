import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface Topic {
  topic: string;
  count: number;
  avg_score: number;
  max_score: number;
  percentage: number;
}

interface TopicOverview {
  topics: Topic[];
  total_items: number;
  total_topics: number;
  threshold: number;
}

interface TopicFilterProps {
  dataSource: string; // 'tweets', 'likes', 'replies', 'bookmarks'
  onFilterChange: (filteredData: any[]) => void;
  onLoadingChange?: (isLoading: boolean) => void;
  onErrorChange?: (error: string | null) => void;
  className?: string;
  showAnalyzeButton?: boolean;
  showCustomTopics?: boolean;
}

interface FilterState {
  mode: 'topic' | 'search' | 'overview';
  selectedTopics: string[];
  excludeTopics: string[];
  minScore: number;
  maxResults: number;
  sortBy: 'score' | 'date' | 'relevance';
  searchQuery: string;
}

export function TopicFilter({
  dataSource,
  onFilterChange,
  onLoadingChange,
  onErrorChange,
  className = '',
  showAnalyzeButton = true,
  showCustomTopics = false
}: TopicFilterProps) {
  const [filterState, setFilterState] = useState<FilterState>({
    mode: 'topic',
    selectedTopics: [],
    excludeTopics: [],
    minScore: 0.3,
    maxResults: 100,
    sortBy: 'score',
    searchQuery: ''
  });

  const [customTopic, setCustomTopic] = useState({
    name: '',
    phrases: ['']
  });

  const queryClient = useQueryClient();

  // Fetch topic overview
  const { data: topicOverview } = useQuery<TopicOverview>({
    queryKey: ['topic-overview'],
    queryFn: async () => {
      const { data } = await axios.get('http://localhost:8000/api/topics/overview');
      return data;
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Filter data mutation
  const { mutate: filterData, isPending: isFiltering } = useMutation({
    mutationFn: async (filterConfig: FilterState) => {
      if (filterConfig.mode === 'search' && filterConfig.searchQuery.trim()) {
        const { data } = await axios.get('http://localhost:8000/api/topics/search', {
          params: {
            query: filterConfig.searchQuery.trim(),
            data_source: dataSource,
            limit: filterConfig.maxResults
          }
        });
        return data.results;
      } else if (filterConfig.mode === 'topic' && filterConfig.selectedTopics.length > 0) {
        const { data } = await axios.post('http://localhost:8000/api/topics/filter', {
          data_source: dataSource,
          topics: filterConfig.selectedTopics,
          exclude_topics: filterConfig.excludeTopics,
          min_score: filterConfig.minScore,
          max_results: filterConfig.maxResults,
          sort_by: filterConfig.sortBy
        });
        return data.results;
      } else {
        // Return empty array for no filters
        return [];
      }
    },
    onSuccess: (data) => {
      onFilterChange(data);
      onLoadingChange?.(false);
      onErrorChange?.(null);
    },
    onError: (error: any) => {
      onErrorChange?.(error.response?.data?.detail || 'Failed to filter data');
      onLoadingChange?.(false);
    }
  });

  // Analyze data source mutation
  const { mutate: analyzeDataSource, isPending: isAnalyzing } = useMutation({
    mutationFn: async () => {
      const { data } = await axios.get(`http://localhost:8000/api/topics/analyze/${dataSource}`, {
        params: { limit: 200 }
      });
      return data;
    },
    onSuccess: () => {
      // Refresh topic overview after analysis
      queryClient.invalidateQueries({ queryKey: ['topic-overview'] });
    }
  });

  // Add custom topic mutation
  const { mutate: addCustomTopic, isPending: isAddingTopic } = useMutation({
    mutationFn: async (topic: { name: string; phrases: string[] }) => {
      const { data } = await axios.post('http://localhost:8000/api/topics/add-custom', {
        topic_name: topic.name,
        seed_phrases: topic.phrases.filter(p => p.trim())
      });
      return data;
    },
    onSuccess: () => {
      setCustomTopic({ name: '', phrases: [''] });
      queryClient.invalidateQueries({ queryKey: ['topic-overview'] });
    }
  });

  // Update loading state
  useEffect(() => {
    onLoadingChange?.(isFiltering || isAnalyzing);
  }, [isFiltering, isAnalyzing, onLoadingChange]);

  // Apply filters when state changes
  useEffect(() => {
    if (filterState.mode === 'topic' && filterState.selectedTopics.length > 0) {
      filterData(filterState);
    } else if (filterState.mode === 'search' && filterState.searchQuery.trim()) {
      filterData(filterState);
    }
  }, [filterState]);

  const updateFilterState = (updates: Partial<FilterState>) => {
    setFilterState(prev => ({ ...prev, ...updates }));
  };

  const toggleTopic = (topic: string) => {
    const isSelected = filterState.selectedTopics.includes(topic);
    const newSelected = isSelected
      ? filterState.selectedTopics.filter(t => t !== topic)
      : [...filterState.selectedTopics, topic];
    
    updateFilterState({ selectedTopics: newSelected });
  };

  const toggleExcludeTopic = (topic: string) => {
    const isExcluded = filterState.excludeTopics.includes(topic);
    const newExcluded = isExcluded
      ? filterState.excludeTopics.filter(t => t !== topic)
      : [...filterState.excludeTopics, topic];
    
    updateFilterState({ excludeTopics: newExcluded });
  };

  const clearFilters = () => {
    setFilterState({
      mode: 'topic',
      selectedTopics: [],
      excludeTopics: [],
      minScore: 0.3,
      maxResults: 100,
      sortBy: 'score',
      searchQuery: ''
    });
    onFilterChange([]);
  };

  const addCustomTopicPhrase = () => {
    setCustomTopic(prev => ({
      ...prev,
      phrases: [...prev.phrases, '']
    }));
  };

  const updateCustomTopicPhrase = (index: number, value: string) => {
    setCustomTopic(prev => ({
      ...prev,
      phrases: prev.phrases.map((phrase, i) => i === index ? value : phrase)
    }));
  };

  const removeCustomTopicPhrase = (index: number) => {
    setCustomTopic(prev => ({
      ...prev,
      phrases: prev.phrases.filter((_, i) => i !== index)
    }));
  };

  return (
    <div className={`bg-white border border-gray-200 rounded-lg p-4 space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">
          Topic Analysis - {dataSource.charAt(0).toUpperCase() + dataSource.slice(1)}
        </h3>
        <div className="flex gap-2">
          {showAnalyzeButton && (
            <button
              onClick={() => analyzeDataSource()}
              disabled={isAnalyzing}
              className="px-3 py-1 text-sm bg-green-500 hover:bg-green-600 text-white rounded-md disabled:opacity-50"
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze'}
            </button>
          )}
          <button
            onClick={clearFilters}
            className="px-3 py-1 text-sm bg-gray-500 hover:bg-gray-600 text-white rounded-md"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Mode Selection */}
      <div className="flex gap-2">
        <button
          onClick={() => updateFilterState({ mode: 'topic' })}
          className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
            filterState.mode === 'topic'
              ? 'bg-blue-100 text-blue-700 border border-blue-300'
              : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
          }`}
        >
          Filter by Topic
        </button>
        <button
          onClick={() => updateFilterState({ mode: 'search' })}
          className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
            filterState.mode === 'search'
              ? 'bg-blue-100 text-blue-700 border border-blue-300'
              : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
          }`}
        >
          Semantic Search
        </button>
        <button
          onClick={() => updateFilterState({ mode: 'overview' })}
          className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
            filterState.mode === 'overview'
              ? 'bg-blue-100 text-blue-700 border border-blue-300'
              : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
          }`}
        >
          Overview
        </button>
      </div>

      {/* Topic Filter Mode */}
      {filterState.mode === 'topic' && (
        <div className="space-y-3">
          {/* Available Topics */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Topics to Include:
            </label>
            <div className="flex flex-wrap gap-2">
              {topicOverview?.topics.map((topic) => (
                <button
                  key={topic.topic}
                  onClick={() => toggleTopic(topic.topic)}
                  className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
                    filterState.selectedTopics.includes(topic.topic)
                      ? 'bg-blue-100 text-blue-700 border border-blue-300'
                      : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                  }`}
                >
                  {topic.topic} ({topic.count})
                </button>
              ))}
            </div>
          </div>

          {/* Exclude Topics */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Exclude Topics:
            </label>
            <div className="flex flex-wrap gap-2">
              {topicOverview?.topics.map((topic) => (
                <button
                  key={topic.topic}
                  onClick={() => toggleExcludeTopic(topic.topic)}
                  className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
                    filterState.excludeTopics.includes(topic.topic)
                      ? 'bg-red-100 text-red-700 border border-red-300'
                      : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                  }`}
                >
                  {topic.topic}
                </button>
              ))}
            </div>
          </div>

          {/* Score Threshold */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700">
              Min Score: {filterState.minScore.toFixed(2)}
            </label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={filterState.minScore}
              onChange={(e) => updateFilterState({ minScore: parseFloat(e.target.value) })}
              className="flex-1 max-w-xs"
            />
          </div>

          {/* Sort Options */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700">Sort by:</label>
            <select
              value={filterState.sortBy}
              onChange={(e) => updateFilterState({ sortBy: e.target.value as any })}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md"
            >
              <option value="score">Score</option>
              <option value="date">Date</option>
              <option value="relevance">Relevance</option>
            </select>
          </div>
        </div>
      )}

      {/* Search Mode */}
      {filterState.mode === 'search' && (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Semantic Search Query:
            </label>
            <input
              type="text"
              placeholder={`Search ${dataSource} semantically (e.g., 'AI and technology', 'Miami beaches', 'political news')...`}
              value={filterState.searchQuery}
              onChange={(e) => updateFilterState({ searchQuery: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Semantic search finds content similar in meaning to your query, not just keyword matches.
            </p>
          </div>
        </div>
      )}

      {/* Overview Mode */}
      {filterState.mode === 'overview' && topicOverview && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="bg-blue-50 p-3 rounded-lg">
              <div className="font-semibold text-blue-700">Total Items</div>
              <div className="text-2xl font-bold text-blue-900">{topicOverview.total_items}</div>
            </div>
            <div className="bg-green-50 p-3 rounded-lg">
              <div className="font-semibold text-green-700">Topics</div>
              <div className="text-2xl font-bold text-green-900">{topicOverview.total_topics}</div>
            </div>
            <div className="bg-purple-50 p-3 rounded-lg">
              <div className="font-semibold text-purple-700">Threshold</div>
              <div className="text-2xl font-bold text-purple-900">{topicOverview.threshold}</div>
            </div>
            <div className="bg-orange-50 p-3 rounded-lg">
              <div className="font-semibold text-orange-700">Data Source</div>
              <div className="text-lg font-bold text-orange-900 capitalize">{dataSource}</div>
            </div>
          </div>

          <div className="space-y-2">
            <h4 className="font-medium text-gray-900">Topic Distribution:</h4>
            {topicOverview.topics.map((topic) => (
              <div key={topic.topic} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div className="flex items-center gap-3">
                  <span className="font-medium capitalize">{topic.topic}</span>
                  <span className="text-sm text-gray-600">({topic.percentage}%)</span>
                </div>
                <div className="text-sm text-gray-600">
                  {topic.count} items • avg: {topic.avg_score}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Custom Topics Section */}
      {showCustomTopics && (
        <div className="border-t pt-4 space-y-3">
          <h4 className="font-medium text-gray-900">Add Custom Topic:</h4>
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Topic name (e.g., 'crypto', 'fitness')"
              value={customTopic.name}
              onChange={(e) => setCustomTopic(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
            />
            {customTopic.phrases.map((phrase, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Seed phrase (e.g., 'cryptocurrency and blockchain')"
                  value={phrase}
                  onChange={(e) => updateCustomTopicPhrase(index, e.target.value)}
                  className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md"
                />
                {customTopic.phrases.length > 1 && (
                  <button
                    onClick={() => removeCustomTopicPhrase(index)}
                    className="px-2 py-2 text-red-600 hover:bg-red-50 rounded-md"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
            <div className="flex gap-2">
              <button
                onClick={addCustomTopicPhrase}
                className="px-3 py-1 text-sm bg-gray-500 hover:bg-gray-600 text-white rounded-md"
              >
                Add Phrase
              </button>
              <button
                onClick={() => addCustomTopic(customTopic)}
                disabled={!customTopic.name.trim() || !customTopic.phrases.some(p => p.trim()) || isAddingTopic}
                className="px-3 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded-md disabled:opacity-50"
              >
                {isAddingTopic ? 'Adding...' : 'Add Topic'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filter Summary */}
      {(filterState.selectedTopics.length > 0 || filterState.searchQuery.trim()) && (
        <div className="bg-blue-50 p-3 rounded-lg">
          <div className="text-sm font-medium text-blue-700 mb-1">Active Filters:</div>
          <div className="text-sm text-blue-600">
            {filterState.mode === 'topic' && filterState.selectedTopics.length > 0 && (
              <div>Topics: {filterState.selectedTopics.join(', ')}</div>
            )}
            {filterState.mode === 'search' && filterState.searchQuery.trim() && (
              <div>Search: "{filterState.searchQuery}"</div>
            )}
            {filterState.excludeTopics.length > 0 && (
              <div>Excluding: {filterState.excludeTopics.join(', ')}</div>
            )}
            <div>Min Score: {filterState.minScore} • Sort: {filterState.sortBy}</div>
          </div>
        </div>
      )}
    </div>
  );
} 