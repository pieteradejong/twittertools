import { useState } from 'react';
import { TopicFilter } from '../common/TopicFilter';
import { TweetListBase, type TweetData } from './TweetListBase';

interface TopicAnalysisViewProps {
  dataSource: string; // 'tweets', 'likes', 'replies', 'bookmarks'
  isActive: boolean;
  title?: string;
  showCustomTopics?: boolean;
  className?: string;
}

interface FilteredDataItem {
  tweet_id?: string;
  id?: string;
  text?: string;
  full_text?: string;
  created_at?: string;
  metrics?: {
    like_count?: number;
    retweet_count?: number;
    reply_count?: number;
    quote_count?: number;
  };
  author?: {
    id?: string;
    username?: string;
    display_name?: string;
    avatar_url?: string;
    verified?: boolean;
  };
  score?: number;
  semantic_score?: number;
  topic?: string;
  filter_topic?: string;
  similarity_score?: number;
}

export function TopicAnalysisView({
  dataSource,
  isActive,
  title,
  showCustomTopics = false,
  className = ''
}: TopicAnalysisViewProps) {
  const [filteredData, setFilteredData] = useState<FilteredDataItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isActive) return null;

  // Convert filtered data to TweetData format for display
  const convertToTweetData = (data: FilteredDataItem[]): TweetData[] => {
    return data.map((item) => ({
      id: item.tweet_id || item.id || '',
      text: item.text || item.full_text || '',
      created_at: item.created_at || '',
      metrics: item.metrics || {
        like_count: 0,
        retweet_count: 0,
        reply_count: 0
      },
      author: item.author || undefined,
      semantic_score: item.score || item.semantic_score,
      topic: item.topic || item.filter_topic,
      similarity_score: item.similarity_score
    }));
  };

  const tweets = convertToTweetData(filteredData);

  const headerContent = (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold text-gray-900">
          {title || `Topic Analysis - ${dataSource.charAt(0).toUpperCase() + dataSource.slice(1)}`}
        </h1>
      </div>

      {/* Topic Filter Component */}
      <TopicFilter
        dataSource={dataSource}
        onFilterChange={setFilteredData}
        onLoadingChange={setIsLoading}
        onErrorChange={setError}
        showAnalyzeButton={true}
        showCustomTopics={showCustomTopics}
      />

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="text-red-700 text-sm font-medium">Error:</div>
          <div className="text-red-600 text-sm">{error}</div>
        </div>
      )}
    </div>
  );

  const resultsSummaryContent = (
    <p className="text-sm text-gray-600">
      {filteredData.length > 0 ? (
        <>Found {filteredData.length} {dataSource} matching your criteria</>
      ) : (
        <>No {dataSource} found matching your criteria</>
      )}
    </p>
  );

  const emptyState = {
    icon: "🔍",
    title: filteredData.length === 0 && !isLoading ? 
      `No ${dataSource} found matching your criteria` : 
      `No ${dataSource} available`,
    description: filteredData.length === 0 && !isLoading ?
      'Try adjusting your topic filters or running analysis first' :
      `Try running topic analysis to classify your ${dataSource}`
  };

  const loadingMessage = `Analyzing ${dataSource}...`;

  return (
    <div className={`h-full ${className}`}>
      <TweetListBase
        tweets={tweets}
        isLoading={isLoading}
        error={null}
        onRefresh={() => {}}
        isActive={isActive}
        headerContent={headerContent}
        resultsSummaryContent={resultsSummaryContent}
        emptyState={emptyState}
        loadingMessage={loadingMessage}
        showResultsSummary={filteredData.length > 0}
      />
    </div>
  );
} 