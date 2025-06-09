import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useState } from 'react';
import { TweetListBase, type TweetData } from './TweetListBase';

interface SimpleTweetListProps {
  isActive: boolean;
  type?: 'likes' | 'bookmarks';
}

export function SimpleTweetList({ isActive, type }: SimpleTweetListProps) {
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

  // Header content
  const headerContent = (
    <div className="flex justify-between items-center">
      <div>
        {/* Empty div for spacing */}
      </div>
      <button 
        className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors" 
        onClick={() => refetch()}
        disabled={isLoading}
      >
        {isLoading ? 'Loading...' : 'Refresh'}
      </button>
    </div>
  );

  // Pagination controls
  const paginationControls = (
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
        onClick={() => setPage((p) => (tweets && tweets.length === limit ? p + 1 : p))}
        disabled={!tweets || tweets.length < limit}
      >
        Next
      </button>
    </div>
  );

  // Empty state configuration
  const emptyState = {
    icon: type === 'likes' ? '💙' : type === 'bookmarks' ? '📖' : '🎉',
    title: type === 'likes' ? 'No likes yet!' : 
           type === 'bookmarks' ? 'No bookmarks yet!' : 
           'No zero engagement tweets found!',
    description: type === 'likes' ? 'Start liking some tweets to see them here.' : 
                 type === 'bookmarks' ? 'Start bookmarking tweets to see them here.' : 
                 'All your tweets have engagement.'
  };

  const loadingMessage = type === 'likes' ? 'Loading likes...' : 
                        type === 'bookmarks' ? 'Loading bookmarks...' : 
                        'Loading tweets...';

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
      paginationControls={paginationControls}
    />
  );
} 