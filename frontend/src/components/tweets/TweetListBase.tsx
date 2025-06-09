import { Tweet } from './Tweet';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { EmptyState } from '../common/EmptyState';
import type { ReactNode } from 'react';

export interface TweetData {
  id: string;
  text: string;
  created_at: string;
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
  semantic_score?: number;
  topic?: string;
  similarity_score?: number;
}

interface TweetListBaseProps {
  tweets?: TweetData[];
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isActive: boolean;
  
  // Customization props
  headerContent?: ReactNode;
  loadingMessage?: string;
  errorMessage?: string;
  emptyState?: {
    icon: string;
    title: string;
    description: string;
  };
  showResultsSummary?: boolean;
  resultsSummaryContent?: ReactNode;
  paginationControls?: ReactNode;
}

export function TweetListBase({
  tweets,
  isLoading,
  error,
  onRefresh,
  isActive,
  headerContent,
  loadingMessage = "Loading tweets...",
  errorMessage = "Error loading tweets",
  emptyState = {
    icon: "🎉",
    title: "No tweets found!",
    description: "No tweets to display."
  },
  showResultsSummary = false,
  resultsSummaryContent,
  paginationControls
}: TweetListBaseProps) {
  if (!isActive) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      {headerContent && (
        <div className="bg-white border-b border-gray-200 p-4 sticky top-0 z-10">
          {headerContent}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <LoadingState message={loadingMessage} />
        ) : error ? (
          <ErrorState message={errorMessage} onRetry={onRefresh} />
        ) : !tweets?.length ? (
          <EmptyState 
            icon={emptyState.icon}
            title={emptyState.title}
            description={emptyState.description}
          />
        ) : (
          <>
            {/* Results Summary */}
            {showResultsSummary && resultsSummaryContent && (
              <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
                {resultsSummaryContent}
              </div>
            )}

            {/* Tweet List */}
            <div className="bg-white divide-y divide-gray-200">
              {tweets.map((tweet) => (
                <Tweet
                  key={tweet.id}
                  id={tweet.id}
                  text={tweet.text}
                  created_at={tweet.created_at}
                  metrics={tweet.metrics}
                  author={tweet.author}
                  semantic_score={tweet.semantic_score}
                  topic={tweet.topic}
                  similarity_score={tweet.similarity_score}
                />
              ))}
            </div>

            {/* Pagination Controls */}
            {paginationControls}
          </>
        )}
      </div>
    </div>
  );
} 