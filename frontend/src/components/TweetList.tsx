import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Tweet } from './Tweet';
import { useState } from 'react';

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
  author?: {
    id?: string;
    username?: string;
    display_name?: string;
    avatar_url?: string;
    verified?: boolean;
  };
}

interface TweetListProps {
  isActive: boolean;
  type?: 'likes' | 'bookmarks';
}

export function TweetList({ isActive, type }: TweetListProps) {
  const [page, setPage] = useState(0);
  const limit = 20;
  const fetcher = async ({ pageParam = 0 }) => {
    const offset = pageParam * limit;
    if (type === 'likes') {
      const { data } = await axios.get<TweetData[]>(`http://localhost:8000/api/likes?limit=${limit}&offset=${offset}`);
      return data.filter((tweet: TweetData & { status?: string }) => tweet.status === undefined || tweet.status === 'published');
    } else if (type === 'bookmarks') {
      const { data } = await axios.get<TweetData[]>(`http://localhost:8000/api/bookmarks?limit=${limit}&offset=${offset}`);
      return data.filter((tweet: TweetData & { status?: string }) => tweet.status === undefined || tweet.status === 'published');
    } else {
      const { data } = await axios.get<TweetData[]>(`http://localhost:8000/api/tweets/zero-engagement?limit=${limit}&offset=${offset}`);
      return data.filter((tweet: TweetData & { status?: string }) => tweet.status === undefined || tweet.status === 'published');
    }
  };
  const { data: tweets, isLoading, error, refetch } = useQuery({
    queryKey: ['tweets', type, page],
    queryFn: () => fetcher({ pageParam: page }),
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
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
            {/* Removed: <h1 className="text-xl font-bold text-gray-900">Zero Engagement Tweets</h1> */}
            {/* Removed: <p className="text-sm text-gray-600 mt-1">...</p> */}
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
              <p className="text-gray-500">{type === 'likes' ? 'Loading likes...' : type === 'bookmarks' ? 'Loading bookmarks...' : 'Loading tweets...'}</p>
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
          <>
            <div className="bg-white divide-y divide-gray-200">
              {tweets.map((tweet) => {
                return (
                  <Tweet
                    key={tweet.id}
                    id={tweet.id}
                    text={tweet.text}
                    created_at={tweet.created_at}
                    metrics={tweet.metrics}
                    author={tweet.author}
                  />
                );
              })}
            </div>
            {/* Pagination Controls */}
            <div className="flex justify-between items-center py-4">
              <button
                className="px-4 py-2 rounded bg-gray-100 border border-gray-300 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">Page {page + 1}</span>
              <button
                className="px-4 py-2 rounded bg-gray-100 border border-gray-300 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                onClick={() => setPage((p) => (tweets.length === limit ? p + 1 : p))}
                disabled={tweets.length < limit}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
} 