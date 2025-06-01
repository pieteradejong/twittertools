import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Tweet } from './Tweet';

interface TweetData {
  id: string;
  text: string;
  created_at: string;
  metrics?: {
    like_count?: number;
    retweet_count?: number;
    reply_count?: number;
    quote_count?: number;
  };
}

async function fetchTweets() {
  const { data } = await axios.get<TweetData[]>('http://localhost:8000/api/tweets/zero-engagement');
  return data;
}

interface TweetListProps {
  isActive: boolean;
}

export function TweetList({ isActive }: TweetListProps) {
  const { data: tweets, isLoading, error, refetch } = useQuery({
    queryKey: ['tweets'],
    queryFn: fetchTweets,
    // Only fetch when the tab is active
    enabled: isActive,
    // Cache for 5 minutes
    staleTime: 5 * 60 * 1000,
    // Don't refetch automatically
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 sticky top-0 z-10">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Zero Engagement Tweets</h1>
            <p className="text-sm text-gray-600 mt-1">
              {tweets ? `${tweets.length} tweets with no engagement` : 'Loading...'}
            </p>
          </div>
          <button 
            className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors" 
            onClick={() => refetch()}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading tweets...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <p className="text-red-600 mb-4">Error loading tweets</p>
              <button 
                onClick={() => refetch()}
                className="px-4 py-2 rounded-md bg-red-500 hover:bg-red-600 text-white text-sm"
              >
                Try Again
              </button>
            </div>
          </div>
        ) : !tweets?.length ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="text-6xl mb-4">🎉</div>
              <p className="text-gray-500 text-lg">No zero engagement tweets found!</p>
              <p className="text-gray-400 text-sm mt-2">All your tweets have engagement.</p>
            </div>
          </div>
        ) : (
          <div className="bg-white divide-y divide-gray-200">
            {tweets.map((tweet) => (
              <Tweet
                key={tweet.id}
                id={tweet.id}
                text={tweet.text}
                created_at={tweet.created_at}
                metrics={tweet.metrics}
                onDelete={(id) => {
                  // TODO: Implement delete functionality
                  console.log('Delete tweet:', id);
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
} 